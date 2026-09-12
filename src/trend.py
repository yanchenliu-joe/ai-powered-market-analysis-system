"""Deterministic SPY moving-average and trend-regime calculations."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.preprocessing import (
    DATE_COLUMN,
    PRICE_COLUMN,
    DataValidationError,
    normalize_price_data,
)

TREND_WINDOWS = (20, 50, 200)
ALLOWED_TREND_REGIMES = frozenset(
    {
        "strong_uptrend",
        "uptrend",
        "transition",
        "downtrend",
        "strong_downtrend",
        "insufficient_data",
    }
)
TREND_COLUMNS = [
    DATE_COLUMN,
    PRICE_COLUMN,
    "sma_20",
    "sma_50",
    "sma_200",
    "distance_to_sma_20",
    "distance_to_sma_50",
    "distance_to_sma_200",
    "trend_regime",
]


def classify_trend_regime(
    price: float | None,
    sma_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
) -> str:
    """Classify one row using strict, priority-ordered trend rules."""

    values = (price, sma_20, sma_50, sma_200)
    if any(pd.isna(value) for value in values):
        return "insufficient_data"
    numeric = np.asarray(values, dtype=float)
    if not np.isfinite(numeric).all():
        raise DataValidationError("trend classification values must be finite")

    current, short, medium, long = numeric
    if current > short > medium > long:
        return "strong_uptrend"
    if current < short < medium < long:
        return "strong_downtrend"
    if current > medium and medium > long:
        return "uptrend"
    if current < medium and medium < long:
        return "downtrend"
    return "transition"


def _validate_trend_invariants(trend: pd.DataFrame) -> None:
    missing = [column for column in TREND_COLUMNS if column not in trend]
    if missing:
        raise DataValidationError(
            f"trend data is missing required columns: {', '.join(missing)}"
        )
    if trend[DATE_COLUMN].duplicated().any():
        raise DataValidationError("trend data contains duplicate dates")

    numeric_columns = [column for column in TREND_COLUMNS if column != DATE_COLUMN]
    numeric_columns.remove("trend_regime")
    numeric = trend[numeric_columns]
    finite_values = numeric.to_numpy(dtype=float)
    if np.isinf(finite_values).any():
        raise DataValidationError("trend data must not contain Infinity")
    if not trend["trend_regime"].isin(ALLOWED_TREND_REGIMES).all():
        raise DataValidationError("trend data contains an unsupported regime")


def compute_trend_timeseries(spy_prices: pd.DataFrame) -> pd.DataFrame:
    """Compute deterministic SPY moving averages, distances, and regimes."""

    normalized = normalize_price_data(spy_prices, require_ticker=False)
    if normalized.empty:
        raise DataValidationError("SPY price data must not be empty")

    trend = normalized.copy()
    for window in TREND_WINDOWS:
        moving_average = f"sma_{window}"
        trend[moving_average] = (
            trend[PRICE_COLUMN].rolling(window=window, min_periods=window).mean()
        )
        trend[f"distance_to_sma_{window}"] = (
            trend[PRICE_COLUMN] / trend[moving_average] - 1.0
        )

    trend["trend_regime"] = trend.apply(
        lambda row: classify_trend_regime(
            row[PRICE_COLUMN],
            row["sma_20"],
            row["sma_50"],
            row["sma_200"],
        ),
        axis=1,
    )
    trend = trend.loc[:, TREND_COLUMNS]
    _validate_trend_invariants(trend)
    return trend


def _snapshot_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def latest_trend_snapshot(trend_timeseries: pd.DataFrame) -> dict[str, Any]:
    """Select the latest precomputed trend row without recalculating it."""

    if trend_timeseries.empty:
        raise DataValidationError("trend time series must not be empty")
    trend = trend_timeseries.copy()
    missing = [column for column in TREND_COLUMNS if column not in trend]
    if missing:
        raise DataValidationError(
            f"trend data is missing required columns: {', '.join(missing)}"
        )
    try:
        trend[DATE_COLUMN] = (
            pd.to_datetime(trend[DATE_COLUMN], errors="raise", utc=True)
            .dt.tz_localize(None)
            .dt.normalize()
        )
    except (TypeError, ValueError) as error:
        raise DataValidationError("trend date contains invalid values") from error
    _validate_trend_invariants(trend)

    latest = trend.loc[trend[DATE_COLUMN].idxmax()]
    return {
        "as_of_date": latest[DATE_COLUMN].date().isoformat(),
        **{
            column: _snapshot_value(latest[column])
            for column in TREND_COLUMNS
            if column != DATE_COLUMN
        },
    }
