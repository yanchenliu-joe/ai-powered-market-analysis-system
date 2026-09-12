"""Deterministic synthetic market data for development and fixture runs.

This module is a developer/demo helper. It does not implement production
analytics and must not be used as a live market-data source.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.config import AppConfig

FIXTURE_RUN_ID = "fixture-acceptance"
FIXTURE_START = date(2023, 1, 3)
FIXTURE_END = date(2024, 2, 29)
EQUITY_TICKERS = ("AAA", "BBB", "CCC", "DDD", "EEE")
RNG_SEED = 7


def fixture_calendar(
    start: date = FIXTURE_START, end: date = FIXTURE_END
) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


def synthetic_universe() -> pd.DataFrame:
    return pd.DataFrame({"ticker": list(EQUITY_TICKERS)})


def synthetic_prices(
    tickers: list[str],
    start: date,
    end: date,
    *,
    base: float = 100.0,
) -> pd.DataFrame:
    dates = fixture_calendar(start, end)
    steps = np.arange(len(dates), dtype=float)
    records: list[dict[str, object]] = []
    for index, ticker in enumerate(tickers):
        slope = 0.18 if index % 2 == 0 else -0.09
        cycle = 1.5 * np.sin(steps / 18.0 + index)
        prices = np.clip(base + slope * steps + cycle + 8 * index, 5.0, None)
        records.extend(
            {
                "date": day,
                "ticker": ticker,
                "adjusted_close": float(price),
            }
            for day, price in zip(dates, prices, strict=True)
        )
    return pd.DataFrame(records)


def synthetic_spy(start: date, end: date) -> pd.DataFrame:
    dates = fixture_calendar(start, end)
    steps = np.arange(len(dates), dtype=float)
    prices = 400.0 + 0.35 * steps + 2.0 * np.sin(steps / 21.0)
    return pd.DataFrame({"date": dates, "adjusted_close": prices})


def synthetic_sectors(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    dates = fixture_calendar(start, end)
    steps = np.arange(len(dates) - 1, dtype=float)
    rng = np.random.default_rng(RNG_SEED)
    yield_changes = 0.04 * np.sin(steps / 7.0) + 0.01 * np.cos(steps / 11.0)
    records: list[dict[str, object]] = []
    for sector_index, ticker in enumerate(tickers):
        direction = -1.0 if sector_index % 2 else 1.0
        beta = direction * (0.012 + sector_index * 0.001)
        noise = 0.00015 * rng.standard_normal(len(steps))
        returns = 0.0004 + beta * yield_changes + noise
        prices = 80.0 * np.cumprod(np.concatenate(([1.0], 1.0 + returns)))
        records.extend(
            {
                "date": day,
                "ticker": ticker,
                "adjusted_close": float(price),
            }
            for day, price in zip(dates, prices, strict=True)
        )
    return pd.DataFrame(records)


def synthetic_dgs10(start: date, end: date) -> pd.DataFrame:
    dates = fixture_calendar(start, end)
    steps = np.arange(len(dates) - 1, dtype=float)
    changes = 0.04 * np.sin(steps / 7.0) + 0.01 * np.cos(steps / 11.0)
    levels = np.concatenate(([4.0], 4.0 + np.cumsum(changes)))
    return pd.DataFrame({"date": dates, "yield_percent": levels})


def fixture_universe_provider() -> pd.DataFrame:
    return synthetic_universe()


def fixture_price_provider(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    if len(tickers) == 1 and tickers[0] == "SPY":
        return synthetic_spy(start, end)
    config_like_sectors = set(tickers) <= {
        "XLC",
        "XLY",
        "XLP",
        "XLE",
        "XLF",
        "XLV",
        "XLI",
        "XLK",
        "XLB",
        "XLRE",
        "XLU",
    }
    if config_like_sectors:
        return synthetic_sectors(tickers, start, end)
    return synthetic_prices(tickers, start, end)


def fixture_yield_provider(series: str, start: date, end: date) -> pd.DataFrame:
    del series
    return synthetic_dgs10(start, end)


def fixture_dates_for_config(_config: AppConfig | None = None) -> tuple[date, date]:
    return FIXTURE_START, FIXTURE_END
