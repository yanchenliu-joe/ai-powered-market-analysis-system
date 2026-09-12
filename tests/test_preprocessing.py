"""Tests for deterministic Phase 2 preprocessing contracts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.preprocessing import (
    DataValidationError,
    align_sector_returns_with_yields,
    calculate_equity_returns,
    calculate_yield_changes,
    normalize_dgs10,
    normalize_price_data,
)

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> pd.DataFrame:
    return pd.read_csv(FIXTURES / name)


def test_price_dates_are_timezone_naive_normalized_and_sorted() -> None:
    normalized = normalize_price_data(read_fixture("equity_prices.csv"))

    assert normalized["date"].dt.tz is None
    assert (normalized["date"].dt.time == pd.Timestamp("00:00:00").time()).all()
    assert normalized[["ticker", "date"]].equals(
        normalized[["ticker", "date"]].sort_values(
            ["ticker", "date"], ignore_index=True
        )
    )


def test_duplicate_ticker_date_rows_raise() -> None:
    with pytest.raises(DataValidationError, match="duplicate"):
        normalize_price_data(read_fixture("duplicate_prices.csv"))


def test_duplicate_single_series_dates_raise() -> None:
    duplicated = pd.DataFrame(
        {"date": ["2024-01-02", "2024-01-02"], "adjusted_close": [100, 101]}
    )

    with pytest.raises(DataValidationError, match="duplicate"):
        normalize_price_data(duplicated, require_ticker=False)


@pytest.mark.parametrize(
    ("value", "message"),
    [(0, "greater than zero"), (-1, "greater than zero"), ("bad", "nonnumeric")],
)
def test_invalid_adjusted_prices_raise(value: object, message: str) -> None:
    data = pd.DataFrame(
        {"date": ["2024-01-02"], "ticker": ["AAA"], "adjusted_close": [value]}
    )

    with pytest.raises(DataValidationError, match=message):
        normalize_price_data(data)


def test_valid_adjusted_prices_pass() -> None:
    normalized = normalize_price_data(read_fixture("equity_prices.csv"))

    assert len(normalized) == 6
    assert normalized["adjusted_close"].dtype == float


def test_returns_use_simple_formula_independently_by_ticker() -> None:
    result = calculate_equity_returns(read_fixture("equity_prices.csv"))
    aaa = result[result["ticker"] == "AAA"].reset_index(drop=True)
    bbb = result[result["ticker"] == "BBB"].reset_index(drop=True)

    assert np.isnan(aaa.loc[0, "equity_return"])
    assert np.isnan(bbb.loc[0, "equity_return"])
    assert aaa.loc[1, "equity_return"] == pytest.approx(102 / 100 - 1)
    assert aaa.loc[2, "equity_return"] == pytest.approx(101 / 102 - 1)
    assert bbb.loc[1, "equity_return"] == pytest.approx(55 / 50 - 1)
    assert bbb.loc[2, "equity_return"] == pytest.approx(0)


def test_single_series_returns_preserve_first_missing_value() -> None:
    result = calculate_equity_returns(
        read_fixture("spy_prices.csv"), require_ticker=False
    )

    assert np.isnan(result.loc[0, "equity_return"])
    assert result.loc[1, "equity_return"] == pytest.approx(472 / 470 - 1)


def test_dgs10_change_is_first_difference_in_percentage_points() -> None:
    data = pd.DataFrame(
        {"date": ["2024-01-02", "2024-01-03"], "yield_percent": [4.30, 4.35]}
    )

    result = calculate_yield_changes(data)

    assert result.loc[1, "yield_change"] == pytest.approx(0.05)
    assert result.attrs["yield_unit"] == "percentage_points"


def test_dgs10_missing_values_are_preserved_and_not_forward_filled() -> None:
    result = calculate_yield_changes(read_fixture("dgs10.csv"))

    assert result["yield_percent"].isna().sum() == 1
    assert np.isnan(result.loc[1, "yield_change"])
    assert np.isnan(result.loc[2, "yield_change"])
    assert result.loc[3, "yield_change"] == pytest.approx(-0.10)


def test_duplicate_dgs10_dates_raise() -> None:
    duplicated = pd.DataFrame(
        {"date": ["2024-01-02", "2024-01-02"], "yield_percent": [4.3, 4.4]}
    )

    with pytest.raises(DataValidationError, match="duplicate"):
        normalize_dgs10(duplicated)


def test_nonnumeric_dgs10_value_raises() -> None:
    data = pd.DataFrame({"date": ["2024-01-02"], "yield_percent": ["invalid"]})

    with pytest.raises(DataValidationError, match="nonnumeric"):
        normalize_dgs10(data)


def test_sector_and_yield_alignment_uses_only_common_valid_dates() -> None:
    returns = calculate_equity_returns(read_fixture("sector_prices.csv"))
    changes = calculate_yield_changes(read_fixture("dgs10.csv"))

    aligned = align_sector_returns_with_yields(returns, changes)

    assert aligned["date"].dt.strftime("%Y-%m-%d").unique().tolist() == ["2024-01-05"]
    assert aligned["ticker"].tolist() == ["XLF", "XLK"]
    assert aligned["equity_return"].notna().all()
    assert aligned["yield_change"].notna().all()
    assert aligned.attrs["yield_unit"] == "percentage_points"


def test_alignment_does_not_manufacture_noncommon_dates() -> None:
    returns = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "equity_return": [0.01, 0.02],
        }
    )
    changes = pd.DataFrame(
        {"date": ["2024-01-03", "2024-01-04"], "yield_change": [0.05, 0.02]}
    )

    aligned = align_sector_returns_with_yields(returns, changes)

    assert aligned["date"].dt.strftime("%Y-%m-%d").tolist() == ["2024-01-03"]
