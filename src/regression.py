"""Deterministic one-factor sector rate-sensitivity regressions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.preprocessing import (
    DATE_COLUMN,
    RETURN_COLUMN,
    TICKER_COLUMN,
    YIELD_CHANGE_COLUMN,
    DataValidationError,
    align_sector_returns_with_yields,
    calculate_equity_returns,
    calculate_yield_changes,
)

SIGNIFICANCE_THRESHOLD = 0.05
TEN_BASIS_POINTS_IN_PERCENTAGE_POINTS = 0.10
SENSITIVITY_LABELS = frozenset(
    {
        "positive_significant",
        "negative_significant",
        "positive_not_significant",
        "negative_not_significant",
        "insufficient_data",
    }
)


@dataclass(frozen=True)
class SectorRegressionResult:
    """Serializable result for one sector's yield-sensitivity regression."""

    ticker: str
    alpha: float | None
    beta_yield: float | None
    beta_std_error: float | None
    beta_t_value: float | None
    p_value: float | None
    ci_95_lower: float | None
    ci_95_upper: float | None
    r_squared: float | None
    adjusted_r_squared: float | None
    n_obs: int
    start_date: str | None
    end_date: str | None
    effect_10bp: float | None
    sensitivity_label: str
    status: str
    error_reason: str | None


def classify_sensitivity(
    beta_yield: float | None,
    p_value: float | None,
    *,
    valid: bool = True,
) -> str:
    """Classify beta direction and strict p-value significance."""

    if not valid or beta_yield is None or p_value is None:
        return "insufficient_data"
    if not np.isfinite([beta_yield, p_value]).all():
        return "insufficient_data"
    if not 0 <= p_value <= 1:
        raise ValueError("p_value must be between 0 and 1")
    if np.isclose(beta_yield, 0.0, rtol=0.0, atol=1e-15):
        return "insufficient_data"

    significant = p_value < SIGNIFICANCE_THRESHOLD
    if beta_yield > 0:
        return "positive_significant" if significant else "positive_not_significant"
    return "negative_significant" if significant else "negative_not_significant"


def _date_bounds(data: pd.DataFrame) -> tuple[str | None, str | None]:
    if data.empty:
        return None, None
    return (
        data[DATE_COLUMN].iloc[0].date().isoformat(),
        data[DATE_COLUMN].iloc[-1].date().isoformat(),
    )


def _insufficient_result(
    ticker: str,
    *,
    n_obs: int,
    start_date: str | None,
    end_date: str | None,
    reason: str,
) -> SectorRegressionResult:
    return SectorRegressionResult(
        ticker=ticker,
        alpha=None,
        beta_yield=None,
        beta_std_error=None,
        beta_t_value=None,
        p_value=None,
        ci_95_lower=None,
        ci_95_upper=None,
        r_squared=None,
        adjusted_r_squared=None,
        n_obs=n_obs,
        start_date=start_date,
        end_date=end_date,
        effect_10bp=None,
        sensitivity_label="insufficient_data",
        status="insufficient_data",
        error_reason=reason,
    )


def _prepare_aligned_data(
    aligned_data: pd.DataFrame, regression_window: int
) -> pd.DataFrame:
    required = [DATE_COLUMN, RETURN_COLUMN, YIELD_CHANGE_COLUMN]
    missing = [column for column in required if column not in aligned_data]
    if missing:
        raise DataValidationError(
            f"aligned regression data is missing columns: {', '.join(missing)}"
        )

    prepared = aligned_data.loc[:, required].copy()
    try:
        prepared[DATE_COLUMN] = (
            pd.to_datetime(prepared[DATE_COLUMN], errors="raise", utc=True)
            .dt.tz_localize(None)
            .dt.normalize()
        )
    except (TypeError, ValueError) as error:
        raise DataValidationError("aligned regression dates are invalid") from error
    if prepared[DATE_COLUMN].duplicated().any():
        raise DataValidationError("aligned regression data contains duplicate dates")

    for column in (RETURN_COLUMN, YIELD_CHANGE_COLUMN):
        numeric = pd.to_numeric(prepared[column], errors="coerce")
        invalid = numeric.isna() & prepared[column].notna()
        if invalid.any():
            raise DataValidationError(f"{column} contains nonnumeric values")
        prepared[column] = numeric

    prepared = prepared.dropna(subset=[RETURN_COLUMN, YIELD_CHANGE_COLUMN])
    prepared = prepared.sort_values(DATE_COLUMN, ignore_index=True)
    values = prepared[[RETURN_COLUMN, YIELD_CHANGE_COLUMN]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise DataValidationError("regression inputs must be finite")
    return prepared.tail(regression_window).reset_index(drop=True)


def _validated_model_values(values: dict[str, float]) -> bool:
    if not np.isfinite(list(values.values())).all():
        return False
    if not 0 <= values["p_value"] <= 1:
        return False
    if values["beta_std_error"] < 0:
        return False
    if not 0 <= values["r_squared"] <= 1:
        return False
    if values["ci_95_lower"] > values["ci_95_upper"]:
        return False
    if not values["ci_95_lower"] <= values["beta_yield"] <= values["ci_95_upper"]:
        return False
    return True


def fit_sector_rate_sensitivity(
    aligned_data: pd.DataFrame,
    ticker: str,
    *,
    regression_window: int,
    min_regression_obs: int,
) -> SectorRegressionResult:
    """Fit one intercept-bearing OLS model with HC3 robust inference."""

    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker must not be empty")
    if regression_window <= 0 or min_regression_obs <= 0:
        raise ValueError("regression observation limits must be positive")
    if min_regression_obs > regression_window:
        raise ValueError("min_regression_obs must not exceed regression_window")

    try:
        model_data = _prepare_aligned_data(aligned_data, regression_window)
    except (DataValidationError, TypeError, ValueError) as error:
        return _insufficient_result(
            ticker,
            n_obs=0,
            start_date=None,
            end_date=None,
            reason=str(error),
        )

    n_obs = len(model_data)
    start_date, end_date = _date_bounds(model_data)
    if n_obs < min_regression_obs:
        return _insufficient_result(
            ticker,
            n_obs=n_obs,
            start_date=start_date,
            end_date=end_date,
            reason=(
                f"requires at least {min_regression_obs} common observations; "
                f"received {n_obs}"
            ),
        )

    yield_changes = model_data[YIELD_CHANGE_COLUMN].to_numpy(dtype=float)
    if np.isclose(np.ptp(yield_changes), 0.0, rtol=0.0, atol=1e-15):
        return _insufficient_result(
            ticker,
            n_obs=n_obs,
            start_date=start_date,
            end_date=end_date,
            reason="yield_change has no usable variation",
        )

    design = sm.add_constant(yield_changes, has_constant="add")
    sector_returns = model_data[RETURN_COLUMN].to_numpy(dtype=float)
    try:
        ordinary_result = sm.OLS(sector_returns, design, missing="raise").fit()
        robust_result = ordinary_result.get_robustcov_results(cov_type="HC3")
        confidence_interval = np.asarray(
            robust_result.conf_int(alpha=0.05), dtype=float
        )
        values = {
            "alpha": float(robust_result.params[0]),
            "beta_yield": float(robust_result.params[1]),
            "beta_std_error": float(robust_result.bse[1]),
            "beta_t_value": float(robust_result.tvalues[1]),
            "p_value": float(robust_result.pvalues[1]),
            "ci_95_lower": float(confidence_interval[1, 0]),
            "ci_95_upper": float(confidence_interval[1, 1]),
            "r_squared": float(ordinary_result.rsquared),
            "adjusted_r_squared": float(ordinary_result.rsquared_adj),
        }
    except Exception as error:
        return _insufficient_result(
            ticker,
            n_obs=n_obs,
            start_date=start_date,
            end_date=end_date,
            reason=f"regression failed: {error}",
        )

    if not _validated_model_values(values):
        return _insufficient_result(
            ticker,
            n_obs=n_obs,
            start_date=start_date,
            end_date=end_date,
            reason="regression produced invalid statistics",
        )

    label = classify_sensitivity(values["beta_yield"], values["p_value"])
    if label == "insufficient_data":
        return _insufficient_result(
            ticker,
            n_obs=n_obs,
            start_date=start_date,
            end_date=end_date,
            reason="beta estimate is exactly zero",
        )

    return SectorRegressionResult(
        ticker=ticker,
        alpha=values["alpha"],
        beta_yield=values["beta_yield"],
        beta_std_error=values["beta_std_error"],
        beta_t_value=values["beta_t_value"],
        p_value=values["p_value"],
        ci_95_lower=values["ci_95_lower"],
        ci_95_upper=values["ci_95_upper"],
        r_squared=values["r_squared"],
        adjusted_r_squared=values["adjusted_r_squared"],
        n_obs=n_obs,
        start_date=start_date,
        end_date=end_date,
        effect_10bp=(values["beta_yield"] * TEN_BASIS_POINTS_IN_PERCENTAGE_POINTS),
        sensitivity_label=label,
        status="success",
        error_reason=None,
    )


def _all_insufficient(
    sector_tickers: Sequence[str], reason: str
) -> list[SectorRegressionResult]:
    return [
        _insufficient_result(
            ticker.strip().upper(),
            n_obs=0,
            start_date=None,
            end_date=None,
            reason=reason,
        )
        for ticker in sector_tickers
    ]


def run_sector_regressions(
    sector_prices: pd.DataFrame,
    treasury_yields: pd.DataFrame,
    *,
    sector_tickers: Sequence[str],
    regression_window: int,
    min_regression_obs: int,
) -> list[SectorRegressionResult]:
    """Run isolated regressions in the caller-provided configuration order."""

    expected_tickers = [ticker.strip().upper() for ticker in sector_tickers]
    if not expected_tickers or any(not ticker for ticker in expected_tickers):
        raise ValueError("sector_tickers must contain nonempty values")
    if len(set(expected_tickers)) != len(expected_tickers):
        raise ValueError("sector_tickers must be unique")

    try:
        sector_returns = calculate_equity_returns(sector_prices)
        yield_changes = calculate_yield_changes(treasury_yields)
    except (DataValidationError, KeyError, TypeError, ValueError) as error:
        return _all_insufficient(expected_tickers, str(error))

    results: list[SectorRegressionResult] = []
    for ticker in expected_tickers:
        ticker_returns = sector_returns.loc[
            sector_returns[TICKER_COLUMN] == ticker,
            [DATE_COLUMN, RETURN_COLUMN],
        ]
        try:
            aligned = align_sector_returns_with_yields(ticker_returns, yield_changes)
            result = fit_sector_rate_sensitivity(
                aligned,
                ticker,
                regression_window=regression_window,
                min_regression_obs=min_regression_obs,
            )
        except Exception as error:
            result = _insufficient_result(
                ticker,
                n_obs=0,
                start_date=None,
                end_date=None,
                reason=f"sector regression failed: {error}",
            )
        results.append(result)
    return results
