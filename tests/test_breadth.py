"""Deterministic tests for Phase 3 market-breadth calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.breadth import (
    BREADTH_COLUMNS,
    calculate_ticker_moving_average,
    compute_breadth_timeseries,
    compute_moving_average_participation,
    latest_breadth_snapshot,
)
from src.preprocessing import DataValidationError


def unequal_history_prices() -> pd.DataFrame:
    """Create explicit rising series with 220, 180, and 30 observations."""

    dates = pd.bdate_range("2023-01-02", periods=220)
    records: list[dict[str, object]] = []
    patterns = {
        "A": (0, 100.0, 1.0),
        "B": (40, 200.0, 2.0),
        "C": (190, 300.0, 1.0),
    }
    for ticker, (start, base, step) in patterns.items():
        for offset, day in enumerate(dates[start:]):
            records.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "adjusted_close": base + step * offset,
                }
            )
    return pd.DataFrame(records).sample(frac=1, random_state=7).reset_index(drop=True)


def manual_window_prices() -> pd.DataFrame:
    """Tiny fixture whose two-observation SMA can be checked by hand."""

    return pd.DataFrame(
        [
            {"date": "2024-01-01", "ticker": "A", "adjusted_close": 1.0},
            {"date": "2024-01-02", "ticker": "A", "adjusted_close": 2.0},
            {"date": "2024-01-03", "ticker": "A", "adjusted_close": 3.0},
            {"date": "2024-01-02", "ticker": "B", "adjusted_close": 5.0},
            {"date": "2024-01-03", "ticker": "B", "adjusted_close": 5.0},
            {"date": "2024-01-03", "ticker": "C", "adjusted_close": 9.0},
        ]
    )


def test_required_columns_and_empty_input_are_rejected() -> None:
    with pytest.raises(DataValidationError, match="missing required"):
        compute_breadth_timeseries(pd.DataFrame({"date": ["2024-01-01"]}))

    with pytest.raises(DataValidationError, match="must not be empty"):
        compute_breadth_timeseries(
            pd.DataFrame(columns=["date", "ticker", "adjusted_close"])
        )


def test_sma50_is_per_ticker_and_requires_complete_window() -> None:
    result = calculate_ticker_moving_average(unequal_history_prices(), 50)
    ticker_a = result[result["ticker"] == "A"].reset_index(drop=True)
    ticker_b = result[result["ticker"] == "B"].reset_index(drop=True)

    assert ticker_a.loc[:48, "sma_50"].isna().all()
    assert ticker_b.loc[:48, "sma_50"].isna().all()
    assert ticker_a.loc[49, "sma_50"] == pytest.approx(np.mean(np.arange(100.0, 150.0)))
    assert ticker_b.loc[49, "sma_50"] == pytest.approx(
        np.mean(np.arange(200.0, 300.0, 2.0))
    )


def test_sma200_is_correct_and_requires_200_observations() -> None:
    result = calculate_ticker_moving_average(unequal_history_prices(), 200)
    ticker_a = result[result["ticker"] == "A"].reset_index(drop=True)
    ticker_b = result[result["ticker"] == "B"].reset_index(drop=True)

    assert ticker_a.loc[:198, "sma_200"].isna().all()
    assert ticker_a.loc[199, "sma_200"] == pytest.approx(
        np.mean(np.arange(100.0, 300.0))
    )
    assert ticker_b["sma_200"].isna().all()


def test_manual_participation_verifies_denominator_and_strict_above_rule() -> None:
    participation = compute_moving_average_participation(manual_window_prices(), 2)
    latest = participation.iloc[-1]

    # A: 3 > mean(2, 3); B: 5 == mean(5, 5); C: incomplete.
    assert latest["valid_count"] == 2
    assert latest["above_count"] == 1
    assert latest["pct_above"] == pytest.approx(50.0)


def test_unequal_history_uses_only_complete_window_stocks() -> None:
    breadth = compute_breadth_timeseries(unequal_history_prices())
    latest = breadth.iloc[-1]

    # A and B have SMA50; only A has SMA200; C has neither.
    assert latest["valid_count_50dma"] == 2
    assert latest["above_50dma_count"] == 2
    assert latest["pct_above_50dma"] == pytest.approx(100.0)
    assert latest["valid_count_200dma"] == 1
    assert latest["above_200dma_count"] == 1
    assert latest["pct_above_200dma"] == pytest.approx(100.0)


def test_zero_valid_denominator_produces_missing_percentage() -> None:
    participation = compute_moving_average_participation(manual_window_prices(), 10)

    assert (participation["valid_count"] == 0).all()
    assert participation["pct_above"].isna().all()


def return_classification_prices() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2024-01-01", "ticker": "A", "adjusted_close": 100.0},
            {"date": "2024-01-01", "ticker": "B", "adjusted_close": 100.0},
            {"date": "2024-01-02", "ticker": "A", "adjusted_close": 110.0},
            {"date": "2024-01-02", "ticker": "B", "adjusted_close": 90.0},
            {"date": "2024-01-03", "ticker": "A", "adjusted_close": 110.0},
            {"date": "2024-01-03", "ticker": "B", "adjusted_close": 95.0},
        ]
    )


def test_advancers_decliners_ratio_and_net_advances() -> None:
    breadth = compute_breadth_timeseries(return_classification_prices())
    first, second, third = breadth.iloc[0], breadth.iloc[1], breadth.iloc[2]

    assert first["valid_return_count"] == 0
    assert first["advancers"] == 0
    assert first["decliners"] == 0
    assert np.isnan(first["advance_decline_ratio"])

    assert second["valid_return_count"] == 2
    assert second["advancers"] == 1
    assert second["decliners"] == 1
    assert second["advance_decline_ratio"] == pytest.approx(1.0)
    assert second["net_advances"] == 0

    assert third["valid_return_count"] == 2
    assert third["advancers"] == 1
    assert third["decliners"] == 0
    assert np.isnan(third["advance_decline_ratio"])
    assert not np.isinf(third["advance_decline_ratio"])
    assert third["net_advances"] == 1


def test_momentum_is_twenty_observation_percentage_point_difference() -> None:
    dates = pd.bdate_range("2024-01-02", periods=80)
    prices = pd.DataFrame(
        {
            "date": dates,
            "ticker": "A",
            "adjusted_close": [100.0] * 60 + [120.0] * 20,
        }
    )

    breadth = compute_breadth_timeseries(prices)

    assert breadth.loc[49:68, "breadth_momentum_20d"].isna().all()
    assert breadth.loc[49, "pct_above_50dma"] == pytest.approx(0.0)
    assert breadth.loc[69, "pct_above_50dma"] == pytest.approx(100.0)
    assert breadth.loc[69, "breadth_momentum_20d"] == pytest.approx(100.0)


def test_output_contract_ordering_uniqueness_and_invariants() -> None:
    breadth = compute_breadth_timeseries(unequal_history_prices())

    assert breadth.columns.tolist() == BREADTH_COLUMNS
    assert breadth["date"].is_monotonic_increasing
    assert breadth["date"].is_unique
    for column in ("pct_above_50dma", "pct_above_200dma"):
        assert breadth[column].dropna().between(0, 100).all()
    assert (breadth["above_50dma_count"] <= breadth["valid_count_50dma"]).all()
    assert (breadth["above_200dma_count"] <= breadth["valid_count_200dma"]).all()
    assert (
        breadth["net_advances"] == breadth["advancers"] - breadth["decliners"]
    ).all()
    numeric = breadth.drop(columns="date").select_dtypes(include="number")
    assert not np.isinf(numeric.to_numpy()).any()


def test_latest_snapshot_selects_latest_precomputed_values() -> None:
    breadth = compute_breadth_timeseries(unequal_history_prices())
    latest_index = breadth["date"].idxmax()
    breadth.loc[latest_index, "advancers"] = 7
    breadth.loc[latest_index, "decliners"] = 2
    breadth.loc[latest_index, "valid_return_count"] = 10
    breadth.loc[latest_index, "advance_decline_ratio"] = 3.5
    breadth.loc[latest_index, "net_advances"] = 5
    shuffled = breadth.sample(frac=1, random_state=11).reset_index(drop=True)

    snapshot = latest_breadth_snapshot(shuffled)

    assert (
        snapshot["as_of_date"] == breadth.loc[latest_index, "date"].date().isoformat()
    )
    assert snapshot["advancers"] == 7
    assert snapshot["decliners"] == 2
    assert snapshot["advance_decline_ratio"] == pytest.approx(3.5)
    assert snapshot["net_advances"] == 5
    assert snapshot["status"] == "available"


def test_snapshot_represents_unavailable_values_as_none() -> None:
    breadth = compute_breadth_timeseries(return_classification_prices())

    snapshot = latest_breadth_snapshot(breadth)

    assert snapshot["advance_decline_ratio"] is None
    assert snapshot["pct_above_50dma"] is None
    assert snapshot["pct_above_200dma"] is None
    assert snapshot["breadth_momentum_20d"] is None
    assert snapshot["status"] == "insufficient_data"
    assert "advance_decline_ratio" in snapshot["unavailable_fields"]


def test_snapshot_rejects_empty_or_invalid_precomputed_series() -> None:
    with pytest.raises(DataValidationError, match="must not be empty"):
        latest_breadth_snapshot(pd.DataFrame())

    invalid = compute_breadth_timeseries(return_classification_prices())
    invalid.loc[0, "above_50dma_count"] = 1
    invalid.loc[0, "valid_count_50dma"] = 0
    with pytest.raises(DataValidationError, match="exceeds"):
        latest_breadth_snapshot(invalid)


@pytest.mark.parametrize("window", [0, -1, 2.5, True])
def test_configurable_helper_rejects_invalid_windows(window: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        compute_moving_average_participation(manual_window_prices(), window)  # type: ignore[arg-type]
