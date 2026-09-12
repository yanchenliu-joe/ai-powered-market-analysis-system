"""Tests for Phase 2 providers, caching, and acquisition metadata."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from src.data_loader import (
    CacheError,
    ProviderError,
    load_dgs10,
    load_equity_prices,
    load_sector_prices,
    load_sp500_universe,
    load_spy_prices,
    resolve_default_date_range,
)

START = date(2024, 1, 2)
END = date(2024, 1, 5)
SECTORS = ["XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLK", "XLB", "XLRE", "XLU"]


def adjusted_price_response(
    tickers: list[str], _start: date, _end: date
) -> pd.DataFrame:
    columns = pd.MultiIndex.from_product([["Adj Close"], tickers])
    values = [
        [100.0 + index for index, _ in enumerate(tickers)],
        [101.0 + index for index, _ in enumerate(tickers)],
    ]
    result = pd.DataFrame(
        values,
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        columns=columns,
    )
    result.index.name = "Date"
    return result


def fred_response(_series: str, _start: date, _end: date) -> pd.DataFrame:
    return pd.DataFrame(
        {"DGS10": [4.30, None, 4.35]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )


def test_price_cache_write_read_round_trip_without_network(
    tmp_path: Path,
) -> None:
    provider = Mock(side_effect=adjusted_price_response)
    live = load_equity_prices(
        ["AAA", "BBB"], START, END, cache_directory=tmp_path, provider=provider
    )
    cached = load_equity_prices(
        ["AAA", "BBB"],
        START,
        END,
        cache_directory=tmp_path,
        provider=Mock(side_effect=AssertionError("network must not be called")),
    )

    pd.testing.assert_frame_equal(live.data, cached.data)
    assert provider.call_count == 1
    assert live.metadata.cache_used is False
    assert cached.metadata.cache_used is True
    assert (tmp_path / "equities_2024-01-02_2024-01-05.csv").is_file()
    assert (tmp_path / "equities_2024-01-02_2024-01-05.metadata.json").is_file()


def test_force_refresh_calls_provider_again(tmp_path: Path) -> None:
    provider = Mock(side_effect=adjusted_price_response)
    load_equity_prices(["AAA"], START, END, cache_directory=tmp_path, provider=provider)
    refreshed = load_equity_prices(
        ["AAA"],
        START,
        END,
        cache_directory=tmp_path,
        force_refresh=True,
        provider=provider,
    )

    assert provider.call_count == 2
    assert refreshed.metadata.cache_used is False


def test_price_output_and_metadata_are_canonical(tmp_path: Path) -> None:
    result = load_equity_prices(
        ["AAA", "BBB"],
        START,
        END,
        cache_directory=tmp_path,
        provider=adjusted_price_response,
    )

    assert result.data.columns.tolist() == ["date", "ticker", "adjusted_close"]
    assert result.metadata.provider == "injected_provider"
    assert result.metadata.raw_row_count == 2
    assert result.metadata.cleaned_row_count == 4
    assert result.metadata.price_treatment == "Adj Close from auto_adjust=False"
    assert result.metadata.requested_start == "2024-01-02"
    assert result.metadata.requested_end == "2024-01-05"


def test_spy_output_uses_single_series_contract(tmp_path: Path) -> None:
    result = load_spy_prices(
        START,
        END,
        cache_directory=tmp_path,
        provider=adjusted_price_response,
    )

    assert result.data.columns.tolist() == ["date", "adjusted_close"]
    assert result.metadata.identifier == "SPY"


def test_all_eleven_sector_etfs_can_be_loaded(tmp_path: Path) -> None:
    result = load_sector_prices(
        SECTORS,
        START,
        END,
        cache_directory=tmp_path,
        provider=adjusted_price_response,
    )

    assert sorted(result.data["ticker"].unique()) == sorted(SECTORS)
    assert len(result.data) == 22


def test_partial_ticker_response_records_individual_failure(tmp_path: Path) -> None:
    result = load_equity_prices(
        ["AAA", "BBB"],
        START,
        END,
        cache_directory=tmp_path,
        provider=lambda _tickers, start, end: adjusted_price_response(
            ["AAA"], start, end
        ),
    )

    assert result.data["ticker"].unique().tolist() == ["AAA"]
    assert result.metadata.errors == ["no usable prices returned for BBB"]


def test_cache_rejects_different_requested_tickers(tmp_path: Path) -> None:
    load_equity_prices(
        ["AAA"],
        START,
        END,
        cache_directory=tmp_path,
        provider=adjusted_price_response,
    )

    with pytest.raises(CacheError, match="identifiers"):
        load_equity_prices(
            ["BBB"],
            START,
            END,
            cache_directory=tmp_path,
            provider=adjusted_price_response,
        )


def test_explicitly_adjusted_close_is_accepted(tmp_path: Path) -> None:
    def adjusted_close_provider(
        tickers: list[str], _start: date, _end: date
    ) -> pd.DataFrame:
        result = pd.DataFrame(
            {"Close": [100.0, 101.0]},
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
        result.attrs["close_is_adjusted"] = True
        return result

    result = load_spy_prices(
        START,
        END,
        cache_directory=tmp_path,
        provider=adjusted_close_provider,
    )

    assert result.metadata.price_treatment == "Close explicitly marked auto-adjusted"


def test_unmarked_close_is_rejected(tmp_path: Path) -> None:
    def unadjusted_provider(
        _tickers: list[str], _start: date, _end: date
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {"Close": [100.0]},
            index=pd.to_datetime(["2024-01-02"]),
        )

    with pytest.raises(ProviderError, match="explicitly adjusted"):
        load_spy_prices(
            START,
            END,
            cache_directory=tmp_path,
            provider=unadjusted_provider,
        )


@pytest.mark.parametrize(
    "response",
    [
        pd.DataFrame(),
        pd.DataFrame({"Open": [100.0]}, index=pd.to_datetime(["2024-01-02"])),
    ],
)
def test_empty_or_malformed_price_responses_fail(
    tmp_path: Path, response: pd.DataFrame
) -> None:
    provider = Mock(return_value=response)

    with pytest.raises(ProviderError):
        load_spy_prices(START, END, cache_directory=tmp_path, provider=provider)


def test_dgs10_output_preserves_missing_levels_and_metadata(
    tmp_path: Path,
) -> None:
    result = load_dgs10(START, END, cache_directory=tmp_path, provider=fred_response)

    assert result.data.columns.tolist() == ["date", "yield_percent"]
    assert result.data["yield_percent"].isna().sum() == 1
    assert result.metadata.identifier == "DGS10"
    assert result.metadata.provider == "injected_provider"
    assert result.metadata.cache_used is False
    assert result.metadata.unit == "percentage_points"


def test_malformed_dgs10_response_fails(tmp_path: Path) -> None:
    provider = Mock(
        return_value=pd.DataFrame(
            {"OTHER": [4.3]}, index=pd.to_datetime(["2024-01-02"])
        )
    )

    with pytest.raises(ProviderError, match="missing series"):
        load_dgs10(START, END, cache_directory=tmp_path, provider=provider)


def test_dgs10_cache_hit_does_not_call_provider(tmp_path: Path) -> None:
    load_dgs10(START, END, cache_directory=tmp_path, provider=fred_response)
    cached = load_dgs10(
        START,
        END,
        cache_directory=tmp_path,
        provider=Mock(side_effect=AssertionError("network must not be called")),
    )

    assert cached.metadata.cache_used is True


def test_corrupted_cache_fails_clearly(tmp_path: Path) -> None:
    cache = tmp_path / "spy_2024-01-02_2024-01-05.csv"
    cache.write_text("not,the,canonical,schema\n1,2,3,4\n", encoding="utf-8")

    with pytest.raises(CacheError, match="incomplete"):
        load_spy_prices(START, END, cache_directory=tmp_path)


def test_mocked_sp500_universe_is_normalized_and_cached(tmp_path: Path) -> None:
    provider = Mock(
        return_value=pd.DataFrame(
            {"Symbol": ["BRK.B", " msft ", "AAPL"], "Security": ["B", "M", "A"]}
        )
    )
    live = load_sp500_universe(cache_directory=tmp_path, provider=provider)
    cached = load_sp500_universe(
        cache_directory=tmp_path,
        provider=Mock(side_effect=AssertionError("network must not be called")),
    )

    assert live.data["ticker"].tolist() == ["AAPL", "BRK-B", "MSFT"]
    assert cached.metadata.cache_used is True
    assert live.metadata.limitations
    assert "survivorship bias" in live.metadata.limitations[0]
    assert provider.call_count == 1


def test_force_refresh_universe_calls_provider(tmp_path: Path) -> None:
    provider = Mock(return_value=pd.DataFrame({"Symbol": ["AAPL"]}))
    load_sp500_universe(cache_directory=tmp_path, provider=provider)
    load_sp500_universe(cache_directory=tmp_path, force_refresh=True, provider=provider)

    assert provider.call_count == 2


def test_default_date_range_avoids_current_day_and_weekend() -> None:
    start, end = resolve_default_date_range(date(2024, 1, 8))

    assert start == date(2019, 1, 5)
    assert end == date(2024, 1, 5)
