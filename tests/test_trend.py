"""Deterministic tests for Phase 4 SPY trend analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.preprocessing import DataValidationError
from src.trend import (
    ALLOWED_TREND_REGIMES,
    TREND_COLUMNS,
    classify_trend_regime,
    compute_trend_timeseries,
    latest_trend_snapshot,
)


def increasing_spy_prices(observations: int = 220) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=observations)
    return pd.DataFrame(
        {
            "date": dates[::-1],
            "adjusted_close": np.arange(1.0, observations + 1.0)[::-1],
        }
    )


def test_missing_columns_and_empty_input_raise_clearly() -> None:
    with pytest.raises(DataValidationError, match="missing required"):
        compute_trend_timeseries(pd.DataFrame({"date": ["2024-01-01"]}))

    with pytest.raises(DataValidationError, match="must not be empty"):
        compute_trend_timeseries(pd.DataFrame(columns=["date", "adjusted_close"]))


def test_moving_averages_are_exact_and_require_complete_windows() -> None:
    trend = compute_trend_timeseries(increasing_spy_prices())

    assert trend.loc[:18, "sma_20"].isna().all()
    assert trend.loc[19, "sma_20"] == pytest.approx(np.mean(np.arange(1.0, 21.0)))
    assert trend.loc[:48, "sma_50"].isna().all()
    assert trend.loc[49, "sma_50"] == pytest.approx(np.mean(np.arange(1.0, 51.0)))
    assert trend.loc[:198, "sma_200"].isna().all()
    assert trend.loc[199, "sma_200"] == pytest.approx(np.mean(np.arange(1.0, 201.0)))


def test_distances_use_price_divided_by_sma_minus_one() -> None:
    trend = compute_trend_timeseries(increasing_spy_prices())
    latest = trend.iloc[-1]

    assert latest["distance_to_sma_20"] == pytest.approx(
        latest["adjusted_close"] / latest["sma_20"] - 1
    )
    assert latest["distance_to_sma_50"] == pytest.approx(
        latest["adjusted_close"] / latest["sma_50"] - 1
    )
    assert latest["distance_to_sma_200"] == pytest.approx(
        latest["adjusted_close"] / latest["sma_200"] - 1
    )


@pytest.mark.parametrize(
    ("price", "sma_20", "sma_50", "sma_200", "expected"),
    [
        (120, 115, 110, 100, "strong_uptrend"),
        (112, 108, 110, 100, "uptrend"),
        (90, 95, 100, 110, "strong_downtrend"),
        (98, 102, 100, 110, "downtrend"),
        (105, 103, 100, 110, "transition"),
        (95, 97, 100, 90, "transition"),
    ],
)
def test_exact_regime_rule_boundaries(
    price: float,
    sma_20: float,
    sma_50: float,
    sma_200: float,
    expected: str,
) -> None:
    assert classify_trend_regime(price, sma_20, sma_50, sma_200) == expected


def test_strong_regimes_have_priority_over_ordinary_regimes() -> None:
    assert classify_trend_regime(120, 115, 110, 100) == "strong_uptrend"
    assert classify_trend_regime(80, 85, 90, 100) == "strong_downtrend"


@pytest.mark.parametrize(
    ("price", "sma_20", "sma_50", "sma_200"),
    [
        (None, 110, 100, 90),
        (110, None, 100, 90),
        (110, 105, None, 90),
        (110, 105, 100, None),
        (np.nan, 105, 100, 90),
    ],
)
def test_any_missing_classification_value_is_insufficient_data(
    price: float | None,
    sma_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
) -> None:
    assert classify_trend_regime(price, sma_20, sma_50, sma_200) == "insufficient_data"


def test_early_time_series_rows_are_insufficient_data() -> None:
    trend = compute_trend_timeseries(increasing_spy_prices())

    assert (trend.loc[:198, "trend_regime"] == "insufficient_data").all()
    assert trend.loc[199, "trend_regime"] == "strong_uptrend"


@pytest.mark.parametrize(
    ("price", "sma_20", "sma_50", "sma_200", "expected"),
    [
        (100, 100, 90, 80, "uptrend"),
        (100, 95, 100, 80, "transition"),
        (110, 100, 100, 90, "uptrend"),
        (110, 105, 100, 100, "transition"),
        (100, 100, 100, 100, "transition"),
    ],
)
def test_equality_boundaries_use_strict_comparisons(
    price: float,
    sma_20: float,
    sma_50: float,
    sma_200: float,
    expected: str,
) -> None:
    assert classify_trend_regime(price, sma_20, sma_50, sma_200) == expected


def test_nonfinite_classification_values_raise() -> None:
    with pytest.raises(DataValidationError, match="finite"):
        classify_trend_regime(np.inf, 105, 100, 90)


def test_output_contract_ordering_uniqueness_and_values() -> None:
    trend = compute_trend_timeseries(increasing_spy_prices())

    assert trend.columns.tolist() == TREND_COLUMNS
    assert trend["date"].is_unique
    assert trend["date"].is_monotonic_increasing
    assert trend["trend_regime"].isin(ALLOWED_TREND_REGIMES).all()
    numeric = trend.drop(columns=["date", "trend_regime"])
    assert not np.isinf(numeric.to_numpy()).any()


def test_duplicate_spy_dates_are_rejected() -> None:
    prices = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "adjusted_close": [100.0, 101.0],
        }
    )

    with pytest.raises(DataValidationError, match="duplicate"):
        compute_trend_timeseries(prices)


@pytest.mark.parametrize("price", [0, -1, "invalid", np.inf])
def test_invalid_spy_prices_are_rejected(price: object) -> None:
    prices = pd.DataFrame({"date": ["2024-01-02"], "adjusted_close": [price]})

    with pytest.raises(DataValidationError):
        compute_trend_timeseries(prices)


def test_latest_snapshot_selects_latest_precomputed_row() -> None:
    trend = compute_trend_timeseries(increasing_spy_prices())
    latest_index = trend["date"].idxmax()
    trend.loc[latest_index, "trend_regime"] = "transition"
    trend.loc[latest_index, "distance_to_sma_20"] = 0.123
    shuffled = trend.sample(frac=1, random_state=4).reset_index(drop=True)

    snapshot = latest_trend_snapshot(shuffled)

    assert snapshot["as_of_date"] == trend.loc[latest_index, "date"].date().isoformat()
    assert snapshot["trend_regime"] == "transition"
    assert snapshot["distance_to_sma_20"] == pytest.approx(0.123)


def test_latest_snapshot_converts_missing_values_to_none() -> None:
    trend = compute_trend_timeseries(increasing_spy_prices(10))

    snapshot = latest_trend_snapshot(trend)

    assert snapshot["sma_20"] is None
    assert snapshot["sma_50"] is None
    assert snapshot["sma_200"] is None
    assert snapshot["distance_to_sma_200"] is None
    assert snapshot["trend_regime"] == "insufficient_data"


def test_latest_snapshot_rejects_empty_or_unsupported_regime() -> None:
    with pytest.raises(DataValidationError, match="must not be empty"):
        latest_trend_snapshot(pd.DataFrame())

    trend = compute_trend_timeseries(increasing_spy_prices())
    trend.loc[trend.index[-1], "trend_regime"] = "bullish"
    with pytest.raises(DataValidationError, match="unsupported"):
        latest_trend_snapshot(trend)
