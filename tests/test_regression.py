"""Deterministic tests for Phase 5 sector rate-sensitivity regressions."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

import src.regression as regression_module
from src.config import load_config
from src.preprocessing import (
    align_sector_returns_with_yields,
    calculate_equity_returns,
    calculate_yield_changes,
)
from src.regression import (
    SENSITIVITY_LABELS,
    classify_sensitivity,
    fit_sector_rate_sensitivity,
    run_sector_regressions,
)

SECTORS = ["XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLK", "XLB", "XLRE", "XLU"]


def synthetic_aligned(
    *,
    observations: int = 300,
    alpha: float = 0.001,
    beta: float = -0.02,
    seed: int = 17,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    yield_change = rng.normal(0.0, 0.05, observations)
    noise = rng.normal(0.0, 0.0005, observations)
    equity_return = alpha + beta * yield_change + noise
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2023-01-02", periods=observations),
            "equity_return": equity_return,
            "yield_change": yield_change,
        }
    )


def fit_synthetic(*, beta: float = -0.02, observations: int = 300, seed: int = 17):
    return fit_sector_rate_sensitivity(
        synthetic_aligned(observations=observations, beta=beta, seed=seed),
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )


def batch_inputs(observations: int = 270) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2023-01-02", periods=observations + 1)
    steps = np.arange(observations, dtype=float)
    yield_changes = 0.04 * np.sin(steps / 7.0) + 0.01 * np.cos(steps / 11.0)
    yield_levels = np.concatenate(([4.0], 4.0 + np.cumsum(yield_changes)))
    treasury = pd.DataFrame({"date": dates, "yield_percent": yield_levels})

    price_records: list[dict[str, object]] = []
    for sector_index, ticker in enumerate(SECTORS):
        direction = -1.0 if sector_index % 2 else 1.0
        beta = direction * (0.01 + sector_index * 0.001)
        noise = 0.0002 * np.cos(steps / (5.0 + sector_index))
        returns = 0.0005 + beta * yield_changes + noise
        prices = 100.0 * np.cumprod(np.concatenate(([1.0], 1.0 + returns)))
        price_records.extend(
            {
                "date": day,
                "ticker": ticker,
                "adjusted_close": price,
            }
            for day, price in zip(dates, prices, strict=True)
        )
    sectors = pd.DataFrame(price_records)
    return sectors, treasury


def test_known_negative_beta_and_alpha_are_recovered() -> None:
    result = fit_synthetic(beta=-0.02)

    assert result.status == "success"
    assert result.beta_yield == pytest.approx(-0.02, abs=0.003)
    assert result.alpha == pytest.approx(0.001, abs=0.0002)
    assert result.sensitivity_label == "negative_significant"


def test_known_positive_beta_is_recovered() -> None:
    result = fit_synthetic(beta=0.03, seed=23)

    assert result.status == "success"
    assert result.beta_yield == pytest.approx(0.03, abs=0.003)
    assert result.sensitivity_label == "positive_significant"


def test_coefficients_match_independent_numpy_least_squares() -> None:
    aligned = synthetic_aligned()
    used = aligned.tail(252)
    design = np.column_stack([np.ones(len(used)), used["yield_change"].to_numpy()])
    expected_alpha, expected_beta = np.linalg.lstsq(
        design, used["equity_return"].to_numpy(), rcond=None
    )[0]

    result = fit_sector_rate_sensitivity(
        aligned,
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.alpha == pytest.approx(expected_alpha, abs=1e-12)
    assert result.beta_yield == pytest.approx(expected_beta, abs=1e-12)


def test_hc3_beta_standard_error_matches_statsmodels_reference() -> None:
    aligned = synthetic_aligned().tail(252)
    design = sm.add_constant(aligned["yield_change"].to_numpy(), has_constant="add")
    reference = (
        sm.OLS(aligned["equity_return"].to_numpy(), design)
        .fit()
        .get_robustcov_results(cov_type="HC3")
    )

    result = fit_sector_rate_sensitivity(
        aligned,
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.beta_std_error == pytest.approx(reference.bse[1], abs=1e-14)
    assert result.beta_t_value == pytest.approx(reference.tvalues[1], abs=1e-12)
    assert result.p_value == pytest.approx(reference.pvalues[1], abs=1e-14)
    assert result.ci_95_lower == pytest.approx(reference.conf_int()[1, 0], abs=1e-12)
    assert result.ci_95_upper == pytest.approx(reference.conf_int()[1, 1], abs=1e-12)


def test_valid_result_statistics_and_dates_are_consistent() -> None:
    aligned = synthetic_aligned()
    expected = aligned.tail(252)
    result = fit_synthetic()

    assert result.n_obs == 252
    assert result.start_date == expected.iloc[0]["date"].date().isoformat()
    assert result.end_date == expected.iloc[-1]["date"].date().isoformat()
    assert 0 <= result.p_value <= 1  # type: ignore[operator]
    assert 0 <= result.r_squared <= 1  # type: ignore[operator]
    assert result.adjusted_r_squared <= 1  # type: ignore[operator]
    assert result.ci_95_lower <= result.beta_yield <= result.ci_95_upper  # type: ignore[operator]
    numeric = [
        value
        for key, value in asdict(result).items()
        if key
        in {
            "alpha",
            "beta_yield",
            "beta_std_error",
            "beta_t_value",
            "p_value",
            "ci_95_lower",
            "ci_95_upper",
            "r_squared",
            "adjusted_r_squared",
            "effect_10bp",
        }
    ]
    assert np.isfinite(numeric).all()


def test_effect_10bp_uses_point_one_percentage_points() -> None:
    result = fit_synthetic(beta=-0.02)

    assert result.effect_10bp == pytest.approx(result.beta_yield * 0.10)  # type: ignore[operator]
    assert result.effect_10bp == pytest.approx(-0.002, abs=0.0003)


def test_between_minimum_and_window_uses_all_available_observations() -> None:
    result = fit_synthetic(observations=220)

    assert result.status == "success"
    assert result.n_obs == 220


def test_below_minimum_observations_is_insufficient() -> None:
    result = fit_synthetic(observations=199)

    assert result.sensitivity_label == "insufficient_data"
    assert result.status == "insufficient_data"
    assert result.n_obs == 199
    assert result.beta_yield is None
    assert result.p_value is None
    assert "at least 200" in result.error_reason  # type: ignore[operator]


def test_constant_yield_change_is_insufficient() -> None:
    aligned = synthetic_aligned()
    aligned["yield_change"] = 0.01

    result = fit_sector_rate_sensitivity(
        aligned,
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.sensitivity_label == "insufficient_data"
    assert result.beta_yield is None
    assert "no usable variation" in result.error_reason  # type: ignore[operator]


@pytest.mark.parametrize(
    ("beta", "p_value", "expected"),
    [
        (0.2, 0.01, "positive_significant"),
        (-0.2, 0.01, "negative_significant"),
        (0.2, 0.10, "positive_not_significant"),
        (-0.2, 0.10, "negative_not_significant"),
        (0.2, 0.05, "positive_not_significant"),
        (-0.2, 0.05, "negative_not_significant"),
        (0.0, 0.01, "insufficient_data"),
    ],
)
def test_sensitivity_label_boundaries(
    beta: float, p_value: float, expected: str
) -> None:
    assert classify_sensitivity(beta, p_value) == expected
    assert expected in SENSITIVITY_LABELS


def test_invalid_label_inputs_are_handled() -> None:
    assert classify_sensitivity(None, 0.01) == "insufficient_data"
    assert classify_sensitivity(np.inf, 0.01) == "insufficient_data"
    assert classify_sensitivity(0.1, 0.01, valid=False) == "insufficient_data"
    with pytest.raises(ValueError, match="between 0 and 1"):
        classify_sensitivity(0.1, 1.5)


def test_nonfinite_or_malformed_aligned_data_is_insufficient() -> None:
    nonfinite = synthetic_aligned()
    nonfinite.loc[0, "equity_return"] = np.inf
    result = fit_sector_rate_sensitivity(
        nonfinite,
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )
    malformed = fit_sector_rate_sensitivity(
        pd.DataFrame({"date": ["2024-01-01"]}),
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.status == "insufficient_data"
    assert malformed.status == "insufficient_data"


@pytest.mark.parametrize(
    "aligned",
    [
        pd.DataFrame(columns=["date", "equity_return", "yield_change"]),
        pd.DataFrame(
            {
                "date": ["not-a-date"],
                "equity_return": [0.01],
                "yield_change": [0.02],
            }
        ),
        pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-02"],
                "equity_return": [0.01, 0.02],
                "yield_change": [0.02, 0.03],
            }
        ),
        pd.DataFrame(
            {
                "date": ["2024-01-02"],
                "equity_return": ["invalid"],
                "yield_change": [0.02],
            }
        ),
    ],
)
def test_aligned_data_quality_failures_are_isolated(
    aligned: pd.DataFrame,
) -> None:
    result = fit_sector_rate_sensitivity(
        aligned,
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.status == "insufficient_data"
    assert result.beta_yield is None


def test_invalid_regression_arguments_raise() -> None:
    aligned = synthetic_aligned()

    with pytest.raises(ValueError, match="ticker"):
        fit_sector_rate_sensitivity(
            aligned, "", regression_window=252, min_regression_obs=200
        )
    with pytest.raises(ValueError, match="positive"):
        fit_sector_rate_sensitivity(
            aligned, "XLK", regression_window=0, min_regression_obs=0
        )
    with pytest.raises(ValueError, match="must not exceed"):
        fit_sector_rate_sensitivity(
            aligned, "XLK", regression_window=199, min_regression_obs=200
        )


def test_statsmodels_failure_returns_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_model(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("model failure")

    monkeypatch.setattr(regression_module.sm, "OLS", fail_model)
    result = fit_sector_rate_sensitivity(
        synthetic_aligned(),
        "XLK",
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.status == "insufficient_data"
    assert "regression failed" in result.error_reason  # type: ignore[operator]


def test_batch_preserves_configuration_order_and_all_sectors() -> None:
    sector_prices, treasury = batch_inputs()
    config = load_config(load_env_file=False)

    results = run_sector_regressions(
        sector_prices,
        treasury,
        sector_tickers=config.data.sector_tickers,
        regression_window=config.analysis.regression_window,
        min_regression_obs=config.analysis.min_regression_obs,
    )

    assert [result.ticker for result in results] == SECTORS
    assert len(results) == 11
    assert all(result.status == "success" for result in results)


def test_batch_rejects_invalid_sector_configuration() -> None:
    sector_prices, treasury = batch_inputs()

    with pytest.raises(ValueError, match="nonempty"):
        run_sector_regressions(
            sector_prices,
            treasury,
            sector_tickers=[],
            regression_window=252,
            min_regression_obs=200,
        )
    with pytest.raises(ValueError, match="unique"):
        run_sector_regressions(
            sector_prices,
            treasury,
            sector_tickers=["XLK", "XLK"],
            regression_window=252,
            min_regression_obs=200,
        )


def test_global_input_failure_marks_each_expected_sector_insufficient() -> None:
    _, treasury = batch_inputs()

    results = run_sector_regressions(
        pd.DataFrame({"date": ["2024-01-02"]}),
        treasury,
        sector_tickers=["XLK", "XLF"],
        regression_window=252,
        min_regression_obs=200,
    )

    assert [result.ticker for result in results] == ["XLK", "XLF"]
    assert all(result.status == "insufficient_data" for result in results)


def test_one_insufficient_sector_does_not_discard_others() -> None:
    sector_prices, treasury = batch_inputs()
    xlre_dates = sector_prices.loc[
        sector_prices["ticker"] == "XLRE", "date"
    ].sort_values()
    cutoff = xlre_dates.iloc[150]
    sector_prices = sector_prices[
        (sector_prices["ticker"] != "XLRE") | (sector_prices["date"] <= cutoff)
    ]

    results = run_sector_regressions(
        sector_prices,
        treasury,
        sector_tickers=SECTORS,
        regression_window=252,
        min_regression_obs=200,
    )
    by_ticker = {result.ticker: result for result in results}

    assert by_ticker["XLRE"].status == "insufficient_data"
    assert by_ticker["XLRE"].n_obs == 150
    assert by_ticker["XLK"].status == "success"
    assert by_ticker["XLF"].status == "success"


def test_window_is_applied_after_common_date_alignment() -> None:
    sector_prices, treasury = batch_inputs(observations=300)
    treasury = treasury.drop(index=list(range(10, 50))).reset_index(drop=True)
    returns = calculate_equity_returns(sector_prices[sector_prices["ticker"] == "XLK"])
    changes = calculate_yield_changes(treasury)
    aligned = align_sector_returns_with_yields(returns, changes)
    expected_window = aligned.tail(252)

    [result] = run_sector_regressions(
        sector_prices[sector_prices["ticker"] == "XLK"],
        treasury,
        sector_tickers=["XLK"],
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.n_obs == 252
    assert result.start_date == expected_window.iloc[0]["date"].date().isoformat()
    assert result.end_date == expected_window.iloc[-1]["date"].date().isoformat()
    removed_dates = set(pd.bdate_range("2023-01-02", periods=301)[10:50])
    assert not set(expected_window["date"]).intersection(removed_dates)


def test_missing_treasury_levels_are_not_forward_filled() -> None:
    sector_prices, treasury = batch_inputs(observations=220)
    treasury.loc[[20, 80], "yield_percent"] = np.nan
    returns = calculate_equity_returns(sector_prices[sector_prices["ticker"] == "XLK"])
    changes = calculate_yield_changes(treasury)
    aligned = align_sector_returns_with_yields(returns, changes)

    [result] = run_sector_regressions(
        sector_prices[sector_prices["ticker"] == "XLK"],
        treasury,
        sector_tickers=["XLK"],
        regression_window=252,
        min_regression_obs=200,
    )

    assert result.n_obs == len(aligned)
    assert treasury.loc[20, "date"] not in set(aligned["date"])
    assert treasury.loc[21, "date"] not in set(aligned["date"])
    assert result.status == "success"


def test_phase_two_simple_return_semantics_are_reused() -> None:
    prices = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=3),
            "ticker": "XLK",
            "adjusted_close": [100.0, 110.0, 99.0],
        }
    )

    returns = calculate_equity_returns(prices)

    assert returns.loc[1, "equity_return"] == pytest.approx(0.10)
    assert returns.loc[2, "equity_return"] == pytest.approx(-0.10)
