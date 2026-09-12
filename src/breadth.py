"""Deterministic market-breadth calculations."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.preprocessing import (
    DATE_COLUMN,
    PRICE_COLUMN,
    RETURN_COLUMN,
    TICKER_COLUMN,
    DataValidationError,
    calculate_equity_returns,
    normalize_price_data,
)

SHORT_PARTICIPATION_WINDOW = 50
LONG_PARTICIPATION_WINDOW = 200
BREADTH_MOMENTUM_LAG = 20

BREADTH_COLUMNS = [
    DATE_COLUMN,
    "pct_above_50dma",
    "above_50dma_count",
    "valid_count_50dma",
    "pct_above_200dma",
    "above_200dma_count",
    "valid_count_200dma",
    "advancers",
    "decliners",
    "valid_return_count",
    "advance_decline_ratio",
    "net_advances",
    "breadth_momentum_20d",
]


def _validate_window(window: int) -> None:
    if not isinstance(window, int) or isinstance(window, bool) or window <= 0:
        raise ValueError("moving-average window must be a positive integer")


def _validated_prices(prices: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_price_data(prices)
    if normalized.empty:
        raise DataValidationError("price data must not be empty")
    return normalized


def _ticker_moving_average(
    normalized_prices: pd.DataFrame, window: int
) -> pd.DataFrame:
    moving_average_column = f"sma_{window}"
    result = normalized_prices.copy()
    result[moving_average_column] = result.groupby(TICKER_COLUMN, sort=False)[
        PRICE_COLUMN
    ].transform(lambda values: values.rolling(window=window, min_periods=window).mean())
    return result


def calculate_ticker_moving_average(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Calculate a complete-window SMA independently for every ticker."""

    _validate_window(window)
    return _ticker_moving_average(_validated_prices(prices), window)


def _moving_average_participation(
    normalized_prices: pd.DataFrame, window: int
) -> pd.DataFrame:
    with_average = _ticker_moving_average(normalized_prices, window)
    moving_average_column = f"sma_{window}"
    valid = with_average[moving_average_column].notna()
    above = valid & (with_average[PRICE_COLUMN] > with_average[moving_average_column])
    observations = with_average.assign(_valid=valid, _above=above)
    participation = (
        observations.groupby(DATE_COLUMN, sort=True)
        .agg(above_count=("_above", "sum"), valid_count=("_valid", "sum"))
        .reset_index()
    )
    participation[["above_count", "valid_count"]] = participation[
        ["above_count", "valid_count"]
    ].astype("int64")
    participation["pct_above"] = np.where(
        participation["valid_count"] > 0,
        participation["above_count"] / participation["valid_count"] * 100.0,
        np.nan,
    )
    return participation.loc[
        :, [DATE_COLUMN, "pct_above", "above_count", "valid_count"]
    ]


def compute_moving_average_participation(
    prices: pd.DataFrame, window: int
) -> pd.DataFrame:
    """Compute participation for a configurable complete-window SMA."""

    _validate_window(window)
    return _moving_average_participation(_validated_prices(prices), window)


def _return_breadth(normalized_prices: pd.DataFrame) -> pd.DataFrame:
    returns = calculate_equity_returns(normalized_prices)
    observations = returns.assign(
        _advancer=returns[RETURN_COLUMN] > 0,
        _decliner=returns[RETURN_COLUMN] < 0,
        _valid_return=returns[RETURN_COLUMN].notna(),
    )
    daily = (
        observations.groupby(DATE_COLUMN, sort=True)
        .agg(
            advancers=("_advancer", "sum"),
            decliners=("_decliner", "sum"),
            valid_return_count=("_valid_return", "sum"),
        )
        .reset_index()
    )
    count_columns = ["advancers", "decliners", "valid_return_count"]
    daily[count_columns] = daily[count_columns].astype("int64")
    daily["advance_decline_ratio"] = np.where(
        daily["decliners"] > 0,
        daily["advancers"] / daily["decliners"],
        np.nan,
    )
    daily["net_advances"] = daily["advancers"] - daily["decliners"]
    return daily


def _rename_participation(participation: pd.DataFrame, window: int) -> pd.DataFrame:
    return participation.rename(
        columns={
            "pct_above": f"pct_above_{window}dma",
            "above_count": f"above_{window}dma_count",
            "valid_count": f"valid_count_{window}dma",
        }
    )


def _validate_breadth_invariants(breadth: pd.DataFrame) -> None:
    missing = [column for column in BREADTH_COLUMNS if column not in breadth]
    if missing:
        raise DataValidationError(
            f"breadth data is missing required columns: {', '.join(missing)}"
        )
    if breadth[DATE_COLUMN].duplicated().any():
        raise DataValidationError("breadth data contains duplicate dates")

    for window in (SHORT_PARTICIPATION_WINDOW, LONG_PARTICIPATION_WINDOW):
        percentage = breadth[f"pct_above_{window}dma"].dropna()
        if not percentage.between(0, 100, inclusive="both").all():
            raise DataValidationError(
                f"pct_above_{window}dma must remain between 0 and 100"
            )
        if (
            breadth[f"above_{window}dma_count"] > breadth[f"valid_count_{window}dma"]
        ).any():
            raise DataValidationError(
                f"above_{window}dma_count exceeds its valid count"
            )

    if (breadth[["advancers", "decliners", "valid_return_count"]] < 0).any().any():
        raise DataValidationError("breadth counts must be nonnegative")
    if (
        breadth["advancers"] + breadth["decliners"] > breadth["valid_return_count"]
    ).any():
        raise DataValidationError("advancers and decliners exceed valid return count")
    if not (
        breadth["net_advances"] == breadth["advancers"] - breadth["decliners"]
    ).all():
        raise DataValidationError("net_advances is inconsistent")

    numeric = breadth.drop(columns=DATE_COLUMN).select_dtypes(include="number")
    if np.isinf(numeric.to_numpy(dtype=float)).any():
        raise DataValidationError("breadth data must not contain Infinity")


def compute_breadth_timeseries(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute one deterministic market-breadth row per trading date."""

    normalized = _validated_prices(prices)
    short_participation = _rename_participation(
        _moving_average_participation(normalized, SHORT_PARTICIPATION_WINDOW),
        SHORT_PARTICIPATION_WINDOW,
    )
    long_participation = _rename_participation(
        _moving_average_participation(normalized, LONG_PARTICIPATION_WINDOW),
        LONG_PARTICIPATION_WINDOW,
    )
    return_breadth = _return_breadth(normalized)

    breadth = short_participation.merge(
        long_participation, on=DATE_COLUMN, how="outer", validate="one_to_one"
    ).merge(return_breadth, on=DATE_COLUMN, how="outer", validate="one_to_one")
    breadth = breadth.sort_values(DATE_COLUMN, ignore_index=True)
    breadth["breadth_momentum_20d"] = breadth["pct_above_50dma"] - breadth[
        "pct_above_50dma"
    ].shift(BREADTH_MOMENTUM_LAG)
    breadth = breadth.loc[:, BREADTH_COLUMNS]
    _validate_breadth_invariants(breadth)
    return breadth


def _snapshot_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def latest_breadth_snapshot(breadth_timeseries: pd.DataFrame) -> dict[str, Any]:
    """Select the latest precomputed breadth row without recalculating it."""

    if breadth_timeseries.empty:
        raise DataValidationError("breadth time series must not be empty")
    breadth = breadth_timeseries.copy()
    try:
        breadth[DATE_COLUMN] = (
            pd.to_datetime(breadth[DATE_COLUMN], errors="raise", utc=True)
            .dt.tz_localize(None)
            .dt.normalize()
        )
    except (TypeError, ValueError) as error:
        raise DataValidationError("breadth date contains invalid values") from error
    _validate_breadth_invariants(breadth)

    latest = breadth.loc[breadth[DATE_COLUMN].idxmax()]
    snapshot_fields = [column for column in BREADTH_COLUMNS if column != DATE_COLUMN]
    snapshot = {
        "as_of_date": latest[DATE_COLUMN].date().isoformat(),
        **{field: _snapshot_value(latest[field]) for field in snapshot_fields},
    }
    unavailable = [field for field in snapshot_fields if snapshot[field] is None]
    snapshot["status"] = "insufficient_data" if unavailable else "available"
    snapshot["unavailable_fields"] = unavailable
    return snapshot
