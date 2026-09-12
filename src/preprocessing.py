"""Deterministic market-data validation and preprocessing."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

DATE_COLUMN = "date"
TICKER_COLUMN = "ticker"
PRICE_COLUMN = "adjusted_close"
RETURN_COLUMN = "equity_return"
YIELD_COLUMN = "yield_percent"
YIELD_CHANGE_COLUMN = "yield_change"
YIELD_UNIT = "percentage_points"


class DataValidationError(ValueError):
    """Raised when market data violates a canonical data contract."""


def _require_columns(data: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise DataValidationError(f"missing required columns: {', '.join(missing)}")


def _normalize_dates(values: pd.Series) -> pd.Series:
    try:
        dates = pd.to_datetime(values, errors="raise", utc=True)
    except (TypeError, ValueError) as error:
        raise DataValidationError("date contains invalid values") from error
    return dates.dt.tz_localize(None).dt.normalize()


def _reject_duplicates(data: pd.DataFrame, keys: list[str]) -> None:
    duplicates = data.duplicated(keys, keep=False)
    if duplicates.any():
        examples = data.loc[duplicates, keys].head(3).to_dict("records")
        raise DataValidationError(f"duplicate observations for {keys}: {examples}")


def _validated_prices(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    nonnumeric = numeric.isna() & values.notna()
    if nonnumeric.any():
        raise DataValidationError("adjusted_close contains nonnumeric values")
    if numeric.isna().any():
        raise DataValidationError("adjusted_close contains missing values")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise DataValidationError("adjusted_close must contain finite values")
    if (numeric <= 0).any():
        raise DataValidationError("adjusted_close must be greater than zero")
    return numeric.astype(float)


def normalize_price_data(
    data: pd.DataFrame, *, require_ticker: bool = True
) -> pd.DataFrame:
    """Validate and normalize canonical adjusted-price observations."""

    required = [DATE_COLUMN, PRICE_COLUMN]
    if require_ticker:
        required.insert(1, TICKER_COLUMN)
    _require_columns(data, required)

    normalized = data.loc[:, required].copy()
    normalized[DATE_COLUMN] = _normalize_dates(normalized[DATE_COLUMN])
    normalized[PRICE_COLUMN] = _validated_prices(normalized[PRICE_COLUMN])

    sort_columns = [TICKER_COLUMN, DATE_COLUMN] if require_ticker else [DATE_COLUMN]
    if require_ticker:
        normalized[TICKER_COLUMN] = (
            normalized[TICKER_COLUMN].astype(str).str.strip().str.upper()
        )
        if (normalized[TICKER_COLUMN] == "").any():
            raise DataValidationError("ticker contains empty values")

    _reject_duplicates(normalized, sort_columns)
    return normalized.sort_values(sort_columns, ignore_index=True)


def calculate_equity_returns(
    prices: pd.DataFrame, *, require_ticker: bool = True
) -> pd.DataFrame:
    """Calculate simple daily returns, independently for each ticker."""

    normalized = normalize_price_data(prices, require_ticker=require_ticker)
    result = normalized.copy()
    if require_ticker:
        result[RETURN_COLUMN] = result.groupby(TICKER_COLUMN, sort=False)[
            PRICE_COLUMN
        ].pct_change(fill_method=None)
    else:
        result[RETURN_COLUMN] = result[PRICE_COLUMN].pct_change(fill_method=None)
    return result


def _validated_yields(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.strip()
    missing_markers = text.isna() | text.isin(["", ".", "NA", "N/A"])
    numeric = pd.to_numeric(text.mask(missing_markers), errors="coerce")
    invalid = numeric.isna() & ~missing_markers
    if invalid.any():
        raise DataValidationError("yield_percent contains nonnumeric values")
    finite = numeric.dropna().to_numpy(dtype=float)
    if not np.isfinite(finite).all():
        raise DataValidationError("yield_percent must contain finite values")
    return numeric.astype(float)


def normalize_dgs10(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize DGS10 while preserving legitimate missing observations."""

    required = [DATE_COLUMN, YIELD_COLUMN]
    _require_columns(data, required)
    normalized = data.loc[:, required].copy()
    normalized[DATE_COLUMN] = _normalize_dates(normalized[DATE_COLUMN])
    normalized[YIELD_COLUMN] = _validated_yields(normalized[YIELD_COLUMN])
    _reject_duplicates(normalized, [DATE_COLUMN])
    return normalized.sort_values(DATE_COLUMN, ignore_index=True)


def calculate_yield_changes(yields: pd.DataFrame) -> pd.DataFrame:
    """Calculate DGS10 first differences in percentage points."""

    result = normalize_dgs10(yields)
    result[YIELD_CHANGE_COLUMN] = result[YIELD_COLUMN].diff()
    result.attrs["yield_unit"] = YIELD_UNIT
    return result


def align_sector_returns_with_yields(
    sector_returns: pd.DataFrame, yield_changes: pd.DataFrame
) -> pd.DataFrame:
    """Inner-align valid sector returns and DGS10 changes by common date."""

    return_required = [DATE_COLUMN, RETURN_COLUMN]
    if TICKER_COLUMN in sector_returns.columns:
        return_required.insert(1, TICKER_COLUMN)
    _require_columns(sector_returns, return_required)
    _require_columns(yield_changes, [DATE_COLUMN, YIELD_CHANGE_COLUMN])

    returns = sector_returns.loc[:, return_required].copy()
    changes = yield_changes.loc[:, [DATE_COLUMN, YIELD_CHANGE_COLUMN]].copy()
    returns[DATE_COLUMN] = _normalize_dates(returns[DATE_COLUMN])
    changes[DATE_COLUMN] = _normalize_dates(changes[DATE_COLUMN])
    _reject_duplicates(changes, [DATE_COLUMN])
    return_keys = (
        [TICKER_COLUMN, DATE_COLUMN]
        if TICKER_COLUMN in returns.columns
        else [DATE_COLUMN]
    )
    _reject_duplicates(returns, return_keys)

    aligned = returns.merge(
        changes, on=DATE_COLUMN, how="inner", validate="many_to_one"
    )
    aligned = aligned.dropna(subset=[RETURN_COLUMN, YIELD_CHANGE_COLUMN])
    sort_columns = (
        [TICKER_COLUMN, DATE_COLUMN]
        if TICKER_COLUMN in aligned.columns
        else [DATE_COLUMN]
    )
    aligned = aligned.sort_values(sort_columns, ignore_index=True)
    aligned.attrs["yield_unit"] = YIELD_UNIT
    return aligned
