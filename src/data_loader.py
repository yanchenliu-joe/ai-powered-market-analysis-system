"""Provider acquisition, raw caching, and metadata for market data."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
from pandas_datareader import data as web

from src.config import PROJECT_ROOT
from src.preprocessing import (
    DataValidationError,
    normalize_dgs10,
    normalize_price_data,
)

DEFAULT_CACHE_DIRECTORY = PROJECT_ROOT / "data" / "raw"
SP500_SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SURVIVORSHIP_LIMITATION = (
    "Historical analysis uses the current S&P 500 constituent universe and is "
    "subject to survivorship bias; point-in-time membership is not used."
)

PriceProvider = Callable[[list[str], date, date], pd.DataFrame]
YieldProvider = Callable[[str, date, date], pd.DataFrame]
UniverseProvider = Callable[[], pd.DataFrame]


class DataLoaderError(RuntimeError):
    """Base exception for data acquisition failures."""


class ProviderError(DataLoaderError):
    """Raised when a live provider fails or returns an unusable schema."""


class CacheError(DataLoaderError):
    """Raised when cached data or metadata cannot be read safely."""


@dataclass(frozen=True)
class AcquisitionMetadata:
    """Auditable metadata kept separate from analytical DataFrames."""

    dataset: str
    provider: str
    requested_start: str | None
    requested_end: str | None
    download_timestamp: str
    cache_used: bool
    raw_row_count: int
    cleaned_row_count: int
    identifier: str | list[str]
    price_treatment: str | None = None
    unit: str | None = None
    exclusions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> AcquisitionMetadata:
        try:
            return cls(**values)
        except TypeError as error:
            raise CacheError("cache metadata has an invalid schema") from error


@dataclass(frozen=True)
class DataLoadResult:
    """Canonical data and its acquisition metadata."""

    data: pd.DataFrame
    metadata: AcquisitionMetadata


def resolve_default_date_range(as_of: date | None = None) -> tuple[date, date]:
    """Resolve a testable five-year range ending on a completed weekday."""

    run_date = as_of or date.today()
    end = run_date - timedelta(days=1)
    while end.weekday() >= 5:
        end -= timedelta(days=1)
    try:
        start = end.replace(year=end.year - 5)
    except ValueError:
        start = end.replace(year=end.year - 5, day=28)
    return start, end


def _validate_date_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError("start date must not be after end date")


def _cache_paths(
    cache_directory: Path, dataset: str, start: date | None, end: date | None
) -> tuple[Path, Path]:
    if start is None or end is None:
        stem = dataset
    else:
        stem = f"{dataset}_{start.isoformat()}_{end.isoformat()}"
    return cache_directory / f"{stem}.csv", cache_directory / f"{stem}.metadata.json"


def _write_cache(
    data: pd.DataFrame,
    metadata: AcquisitionMetadata,
    csv_path: Path,
    metadata_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_temporary = csv_path.with_suffix(f"{csv_path.suffix}.tmp")
    metadata_temporary = metadata_path.with_suffix(f"{metadata_path.suffix}.tmp")
    data.to_csv(csv_temporary, index=False, date_format="%Y-%m-%d")
    metadata_temporary.write_text(
        json.dumps(asdict(metadata), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    csv_temporary.replace(csv_path)
    metadata_temporary.replace(metadata_path)


def _read_cache(
    csv_path: Path, metadata_path: Path
) -> tuple[pd.DataFrame, AcquisitionMetadata]:
    if not csv_path.is_file() or not metadata_path.is_file():
        raise CacheError(
            f"cache is incomplete; expected {csv_path.name} and {metadata_path.name}"
        )
    try:
        data = pd.read_csv(csv_path)
        metadata_values = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, pd.errors.ParserError) as error:
        raise CacheError(f"unable to read cache: {csv_path}") from error
    if not isinstance(metadata_values, dict):
        raise CacheError("cache metadata must be a JSON object")
    return data, replace(
        AcquisitionMetadata.from_dict(metadata_values), cache_used=True
    )


def _validate_cache_metadata(
    metadata: AcquisitionMetadata,
    dataset: str,
    identifier: str | list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
) -> None:
    if metadata.dataset != dataset:
        raise CacheError(f"cached metadata does not describe {dataset}")
    if identifier is not None and metadata.identifier != identifier:
        raise CacheError(
            "cached identifiers do not match the request; use force_refresh=True"
        )
    if start is not None and metadata.requested_start != start.isoformat():
        raise CacheError("cached start date does not match the request")
    if end is not None and metadata.requested_end != end.isoformat():
        raise CacheError("cached end date does not match the request")


def _fetch_sp500_universe() -> pd.DataFrame:
    from io import StringIO
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    request = Request(
        SP500_SOURCE_URL,
        headers={"User-Agent": "ai-powered-market-analysis/0.1"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8")
        tables = pd.read_html(StringIO(html))
    except (OSError, ValueError, URLError) as error:
        raise ProviderError("S&P 500 universe provider failed") from error
    if not tables:
        raise ProviderError("S&P 500 universe provider returned no tables")
    return tables[0]


def _normalize_universe(raw: pd.DataFrame) -> pd.DataFrame:
    symbol_column = next(
        (column for column in ("Symbol", "symbol", "ticker") if column in raw.columns),
        None,
    )
    if symbol_column is None:
        raise ProviderError("S&P 500 universe response has no symbol column")
    tickers = (
        raw[symbol_column]
        .astype("string")
        .str.strip()
        .str.upper()
        .str.replace(".", "-", regex=False)
    )
    if tickers.isna().any() or (tickers == "").any():
        raise ProviderError("S&P 500 universe contains empty symbols")
    if tickers.duplicated().any():
        raise ProviderError("S&P 500 universe contains duplicate symbols")
    return pd.DataFrame({"ticker": tickers}).sort_values("ticker", ignore_index=True)


def load_sp500_universe(
    *,
    cache_directory: str | Path = DEFAULT_CACHE_DIRECTORY,
    force_refresh: bool = False,
    provider: UniverseProvider | None = None,
) -> DataLoadResult:
    """Load the current S&P 500 universe from cache or a replaceable provider."""

    cache_dir = Path(cache_directory)
    csv_path, metadata_path = _cache_paths(cache_dir, "sp500_universe", None, None)
    if csv_path.exists() and not force_refresh:
        cached, metadata = _read_cache(csv_path, metadata_path)
        _validate_cache_metadata(metadata, "sp500_universe")
        try:
            normalized = _normalize_universe(cached)
        except (DataLoaderError, KeyError, TypeError, ValueError) as error:
            raise CacheError("cached S&P 500 universe is corrupted") from error
        return DataLoadResult(normalized, metadata)

    fetch = provider or _fetch_sp500_universe
    try:
        raw = fetch()
    except DataLoaderError:
        raise
    except Exception as error:
        raise ProviderError("S&P 500 universe provider failed") from error
    if raw.empty:
        raise ProviderError("S&P 500 universe provider returned no rows")
    normalized = _normalize_universe(raw)
    metadata = AcquisitionMetadata(
        dataset="sp500_universe",
        provider="wikipedia" if provider is None else "injected_provider",
        requested_start=None,
        requested_end=None,
        download_timestamp=datetime.now(UTC).isoformat(),
        cache_used=False,
        raw_row_count=len(raw),
        cleaned_row_count=len(normalized),
        identifier=normalized["ticker"].tolist(),
        limitations=[SURVIVORSHIP_LIMITATION],
    )
    _write_cache(normalized, metadata, csv_path, metadata_path)
    return DataLoadResult(normalized, metadata)


def _fetch_yfinance_prices(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    try:
        data = yf.download(
            tickers=tickers,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            actions=False,
            progress=False,
            group_by="column",
            threads=True,
        )
    except Exception as error:
        raise ProviderError("yfinance price download failed") from error
    data.attrs["price_treatment"] = "Adj Close from auto_adjust=False"
    return data


def _price_matrix(raw: pd.DataFrame, tickers: list[str]) -> tuple[pd.DataFrame, str]:
    if {"date", "adjusted_close"}.issubset(raw.columns):
        canonical = raw.copy()
        if "ticker" not in canonical.columns and len(tickers) == 1:
            canonical["ticker"] = tickers[0]
        if "ticker" not in canonical.columns:
            raise ProviderError(
                "multi-ticker canonical price response is missing ticker"
            )
        return canonical, str(
            raw.attrs.get("price_treatment", "provider adjusted_close")
        )

    label = "Adj Close"
    treatment = "Adj Close from auto_adjust=False"
    close_is_adjusted = raw.attrs.get("close_is_adjusted") is True
    if isinstance(raw.columns, pd.MultiIndex):
        for level in range(raw.columns.nlevels):
            values = raw.columns.get_level_values(level)
            if label in values:
                matrix = raw.xs(label, axis=1, level=level)
                return matrix, treatment
        if close_is_adjusted:
            for level in range(raw.columns.nlevels):
                values = raw.columns.get_level_values(level)
                if "Close" in values:
                    matrix = raw.xs("Close", axis=1, level=level)
                    return matrix, "Close explicitly marked auto-adjusted"
    else:
        if label in raw.columns:
            return raw[[label]].rename(columns={label: tickers[0]}), treatment
        if "Close" in raw.columns and close_is_adjusted:
            return (
                raw[["Close"]].rename(columns={"Close": tickers[0]}),
                "Close explicitly marked auto-adjusted",
            )
    raise ProviderError(
        "price response has neither Adj Close nor explicitly adjusted Close"
    )


def _canonicalize_price_response(
    raw: pd.DataFrame, tickers: list[str]
) -> tuple[pd.DataFrame, str, list[str], int]:
    if raw.empty:
        raise ProviderError("price provider returned an empty response")
    matrix, treatment = _price_matrix(raw, tickers)

    if {"date", "adjusted_close", "ticker"}.issubset(matrix.columns):
        canonical = matrix.loc[:, ["date", "ticker", "adjusted_close"]].copy()
    else:
        if isinstance(matrix, pd.Series):
            matrix = matrix.to_frame(name=tickers[0])
        matrix = matrix.copy()
        matrix.index.name = "date"
        canonical = matrix.reset_index().melt(
            id_vars="date", var_name="ticker", value_name="adjusted_close"
        )

    canonical["ticker"] = (
        canonical["ticker"]
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(".", "-", regex=False)
    )
    expected = {ticker.upper().replace(".", "-") for ticker in tickers}
    available = set(canonical.loc[canonical["adjusted_close"].notna(), "ticker"])
    missing_tickers = sorted(expected - available)
    missing_rows = int(canonical["adjusted_close"].isna().sum())
    canonical = canonical.dropna(subset=["adjusted_close"])
    if canonical.empty:
        raise ProviderError("price provider returned no usable adjusted prices")
    return canonical, treatment, missing_tickers, missing_rows or 0


def _load_prices(
    dataset: str,
    tickers: list[str],
    start: date,
    end: date,
    *,
    cache_directory: str | Path,
    force_refresh: bool,
    provider: PriceProvider | None,
    single_series: bool,
) -> DataLoadResult:
    _validate_date_range(start, end)
    cache_dir = Path(cache_directory)
    csv_path, metadata_path = _cache_paths(cache_dir, dataset, start, end)
    if csv_path.exists() and not force_refresh:
        cached, metadata = _read_cache(csv_path, metadata_path)
        identifier: str | list[str] = tickers[0] if single_series else tickers
        _validate_cache_metadata(metadata, dataset, identifier, start, end)
        try:
            normalized = normalize_price_data(cached, require_ticker=not single_series)
        except (DataValidationError, KeyError, TypeError, ValueError) as error:
            raise CacheError(f"cached {dataset} prices are corrupted") from error
        return DataLoadResult(normalized, metadata)

    fetch = provider or _fetch_yfinance_prices
    try:
        raw = fetch(tickers, start, end)
    except DataLoaderError:
        raise
    except Exception as error:
        raise ProviderError(f"{dataset} price provider failed") from error
    canonical, treatment, missing_tickers, missing_rows = _canonicalize_price_response(
        raw, tickers
    )
    normalized_multi = normalize_price_data(canonical)
    if single_series:
        normalized = normalize_price_data(
            normalized_multi.drop(columns="ticker"), require_ticker=False
        )
    else:
        normalized = normalized_multi

    exclusions = []
    if missing_rows:
        exclusions.append(f"excluded {missing_rows} rows with missing adjusted prices")
    errors = [f"no usable prices returned for {ticker}" for ticker in missing_tickers]
    if single_series and errors:
        raise ProviderError(errors[0])
    metadata = AcquisitionMetadata(
        dataset=dataset,
        provider="yfinance" if provider is None else "injected_provider",
        requested_start=start.isoformat(),
        requested_end=end.isoformat(),
        download_timestamp=datetime.now(UTC).isoformat(),
        cache_used=False,
        raw_row_count=len(raw),
        cleaned_row_count=len(normalized),
        identifier=tickers[0] if single_series else tickers,
        price_treatment=treatment,
        exclusions=exclusions,
        errors=errors,
    )
    _write_cache(normalized, metadata, csv_path, metadata_path)
    return DataLoadResult(normalized, metadata)


def load_equity_prices(
    tickers: list[str],
    start: date,
    end: date,
    *,
    cache_directory: str | Path = DEFAULT_CACHE_DIRECTORY,
    force_refresh: bool = False,
    provider: PriceProvider | None = None,
) -> DataLoadResult:
    """Load canonical adjusted prices for the current equity universe."""

    if not tickers:
        raise ValueError("at least one equity ticker is required")
    return _load_prices(
        "equities",
        tickers,
        start,
        end,
        cache_directory=cache_directory,
        force_refresh=force_refresh,
        provider=provider,
        single_series=False,
    )


def load_spy_prices(
    start: date,
    end: date,
    *,
    ticker: str = "SPY",
    cache_directory: str | Path = DEFAULT_CACHE_DIRECTORY,
    force_refresh: bool = False,
    provider: PriceProvider | None = None,
) -> DataLoadResult:
    """Load canonical adjusted SPY benchmark prices."""

    return _load_prices(
        "spy",
        [ticker],
        start,
        end,
        cache_directory=cache_directory,
        force_refresh=force_refresh,
        provider=provider,
        single_series=True,
    )


def load_sector_prices(
    tickers: list[str],
    start: date,
    end: date,
    *,
    cache_directory: str | Path = DEFAULT_CACHE_DIRECTORY,
    force_refresh: bool = False,
    provider: PriceProvider | None = None,
) -> DataLoadResult:
    """Load canonical adjusted prices for the configured sector ETFs."""

    if not tickers:
        raise ValueError("at least one sector ticker is required")
    return _load_prices(
        "sectors",
        tickers,
        start,
        end,
        cache_directory=cache_directory,
        force_refresh=force_refresh,
        provider=provider,
        single_series=False,
    )


def _fetch_fred_yields(series: str, start: date, end: date) -> pd.DataFrame:
    try:
        return web.DataReader(series, "fred", start, end)
    except Exception as error:
        raise ProviderError(f"FRED download failed for {series}") from error


def _canonicalize_yield_response(raw: pd.DataFrame, series: str) -> pd.DataFrame:
    if raw.empty:
        raise ProviderError("FRED provider returned an empty response")
    if {"date", "yield_percent"}.issubset(raw.columns):
        return raw.loc[:, ["date", "yield_percent"]].copy()
    if series not in raw.columns:
        raise ProviderError(f"FRED response is missing series column {series}")
    canonical = raw[[series]].reset_index()
    canonical.columns = ["date", "yield_percent"]
    return canonical


def load_dgs10(
    start: date,
    end: date,
    *,
    series: str = "DGS10",
    cache_directory: str | Path = DEFAULT_CACHE_DIRECTORY,
    force_refresh: bool = False,
    provider: YieldProvider | None = None,
) -> DataLoadResult:
    """Load DGS10 levels in percentage points from cache or FRED."""

    _validate_date_range(start, end)
    cache_dir = Path(cache_directory)
    csv_path, metadata_path = _cache_paths(cache_dir, "dgs10", start, end)
    if csv_path.exists() and not force_refresh:
        cached, metadata = _read_cache(csv_path, metadata_path)
        _validate_cache_metadata(metadata, "dgs10", series, start, end)
        try:
            normalized = normalize_dgs10(cached)
        except (DataValidationError, KeyError, TypeError, ValueError) as error:
            raise CacheError("cached DGS10 data is corrupted") from error
        return DataLoadResult(normalized, metadata)

    fetch = provider or _fetch_fred_yields
    try:
        raw = fetch(series, start, end)
    except DataLoaderError:
        raise
    except Exception as error:
        raise ProviderError("DGS10 provider failed") from error
    canonical = _canonicalize_yield_response(raw, series)
    try:
        normalized = normalize_dgs10(canonical)
    except DataValidationError as error:
        raise ProviderError("DGS10 provider returned unusable data") from error
    metadata = AcquisitionMetadata(
        dataset="dgs10",
        provider="fred" if provider is None else "injected_provider",
        requested_start=start.isoformat(),
        requested_end=end.isoformat(),
        download_timestamp=datetime.now(UTC).isoformat(),
        cache_used=False,
        raw_row_count=len(raw),
        cleaned_row_count=len(normalized),
        identifier=series,
        price_treatment=None,
        unit="percentage_points",
    )
    _write_cache(normalized, metadata, csv_path, metadata_path)
    return DataLoadResult(normalized, metadata)
