"""Orchestration and strict serialization for deterministic quant output."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from pydantic import ValidationError

from src.breadth import compute_breadth_timeseries, latest_breadth_snapshot
from src.config import AppConfig
from src.data_loader import AcquisitionMetadata
from src.regression import run_sector_regressions
from src.schemas import (
    SCHEMA_VERSION,
    BreadthStatus,
    DataQuality,
    DataSources,
    QuantStatus,
    QuantSummary,
    RunMetadata,
    SectorRegressionSummary,
    TrendRegime,
)
from src.trend import compute_trend_timeseries, latest_trend_snapshot

SURVIVORSHIP_LIMITATION = (
    "Historical breadth may use the current S&P 500 constituent universe and "
    "is therefore subject to survivorship bias."
)
ASSOCIATION_LIMITATION = (
    "Sector regressions estimate statistical association, not causation."
)
OMITTED_FACTORS_LIMITATION = (
    "Daily one-factor sector regressions omit other market and macroeconomic "
    "factors."
)


class QuantPipelineError(RuntimeError):
    """Critical quantitative-stage failure that prevents a valid summary."""

    status = QuantStatus.FAILURE


@dataclass(frozen=True)
class AcquisitionContext:
    """Typed acquisition metadata required for auditable quant output."""

    universe: AcquisitionMetadata
    equities: AcquisitionMetadata
    spy: AcquisitionMetadata
    sectors: AcquisitionMetadata
    treasury: AcquisitionMetadata


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if np.isnan(value):
            return None
        if not np.isfinite(value):
            raise QuantPipelineError("quantitative output contains Infinity")
    return value


def _combined_provider(metadata: list[AcquisitionMetadata]) -> str:
    providers = sorted({item.provider for item in metadata if item.provider})
    if not providers:
        raise QuantPipelineError("acquisition metadata has no provider")
    return ",".join(providers)


def _unique_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _actual_common_as_of(
    breadth_timeseries: pd.DataFrame, trend_timeseries: pd.DataFrame
) -> pd.Timestamp:
    breadth_dates = pd.DatetimeIndex(breadth_timeseries["date"])
    trend_dates = pd.DatetimeIndex(trend_timeseries["date"])
    common_dates = breadth_dates.intersection(trend_dates)
    if common_dates.empty:
        raise QuantPipelineError(
            "breadth and trend outputs have no common supported date"
        )
    return common_dates.max()


def _validate_core_snapshots(breadth: dict[str, Any], trend: dict[str, Any]) -> None:
    required_breadth = (
        "pct_above_50dma",
        "pct_above_200dma",
        "breadth_momentum_20d",
    )
    if any(breadth[field] is None for field in required_breadth):
        raise QuantPipelineError("latest breadth snapshot is not usable")
    if trend["trend_regime"] == TrendRegime.INSUFFICIENT_DATA:
        raise QuantPipelineError("latest trend snapshot is not usable")


def _build_data_quality(
    *,
    equity_prices: pd.DataFrame,
    spy_observation_count: int,
    sector_prices: pd.DataFrame,
    treasury_yields: pd.DataFrame,
    breadth: dict[str, Any],
    sector_results: list[SectorRegressionSummary],
    context: AcquisitionContext,
    analysis_start: date,
    analysis_end: date,
) -> DataQuality:
    metadata_items = [
        context.universe,
        context.equities,
        context.spy,
        context.sectors,
        context.treasury,
    ]
    exclusions = _unique_strings(
        [exclusion for metadata in metadata_items for exclusion in metadata.exclusions]
    )
    warnings = _unique_strings(
        [warning for metadata in metadata_items for warning in metadata.errors]
        + [
            f"{result.ticker}: {result.error_reason}"
            for result in sector_results
            if result.status == "insufficient_data" and result.error_reason
        ]
    )
    valid_sector_count = sum(result.status == "success" for result in sector_results)
    insufficient_sector_count = len(sector_results) - valid_sector_count
    universe_size = context.universe.cleaned_row_count
    return DataQuality(
        requested_start=analysis_start,
        requested_end=analysis_end,
        equity_raw_row_count=context.equities.raw_row_count,
        equity_cleaned_row_count=context.equities.cleaned_row_count,
        available_equity_tickers=int(equity_prices["ticker"].nunique()),
        universe_size=universe_size,
        latest_50dma_valid_count=breadth["valid_count_50dma"],
        latest_200dma_valid_count=breadth["valid_count_200dma"],
        spy_raw_row_count=context.spy.raw_row_count,
        spy_cleaned_row_count=context.spy.cleaned_row_count,
        spy_observation_count=spy_observation_count,
        dgs10_raw_row_count=context.treasury.raw_row_count,
        dgs10_cleaned_row_count=context.treasury.cleaned_row_count,
        dgs10_usable_observation_count=int(
            treasury_yields["yield_percent"].notna().sum()
        ),
        sector_raw_row_count=context.sectors.raw_row_count,
        sector_cleaned_row_count=context.sectors.cleaned_row_count,
        available_sector_tickers=int(sector_prices["ticker"].nunique()),
        sector_result_count=len(sector_results),
        valid_sector_count=valid_sector_count,
        insufficient_sector_count=insufficient_sector_count,
        exclusions=exclusions,
        warnings=warnings,
    )


def _build_limitations(context: AcquisitionContext) -> list[str]:
    metadata_limitations = [
        limitation
        for metadata in (
            context.universe,
            context.equities,
            context.spy,
            context.sectors,
            context.treasury,
        )
        for limitation in metadata.limitations
    ]
    return _unique_strings(
        [
            SURVIVORSHIP_LIMITATION,
            ASSOCIATION_LIMITATION,
            OMITTED_FACTORS_LIMITATION,
            *metadata_limitations,
        ]
    )


def run_quant_pipeline(
    equity_prices: pd.DataFrame,
    spy_prices: pd.DataFrame,
    sector_prices: pd.DataFrame,
    treasury_yields: pd.DataFrame,
    *,
    config: AppConfig,
    acquisition_context: AcquisitionContext,
    analysis_start: date,
    analysis_end: date,
    run_id: str | None = None,
    generated_at: datetime | None = None,
) -> QuantSummary:
    """Assemble accepted quantitative modules into one validated summary."""

    resolved_run_id = run_id or uuid4().hex
    resolved_generated_at = generated_at or datetime.now(UTC)

    try:
        breadth_timeseries = compute_breadth_timeseries(equity_prices)
        trend_timeseries = compute_trend_timeseries(spy_prices)
    except Exception as error:
        raise QuantPipelineError(
            f"critical breadth or trend stage failed: {error}"
        ) from error

    common_as_of = _actual_common_as_of(breadth_timeseries, trend_timeseries)
    breadth_snapshot = latest_breadth_snapshot(
        breadth_timeseries[breadth_timeseries["date"] <= common_as_of]
    )
    trend_snapshot = latest_trend_snapshot(
        trend_timeseries[trend_timeseries["date"] <= common_as_of]
    )
    _validate_core_snapshots(breadth_snapshot, trend_snapshot)

    regression_results = run_sector_regressions(
        sector_prices,
        treasury_yields,
        sector_tickers=config.data.sector_tickers,
        regression_window=config.analysis.regression_window,
        min_regression_obs=config.analysis.min_regression_obs,
    )
    expected_tickers = config.data.sector_tickers
    if [result.ticker for result in regression_results] != expected_tickers:
        raise QuantPipelineError(
            "sector regression output does not match configured order"
        )

    safe_regressions = [_json_safe(asdict(result)) for result in regression_results]
    try:
        sector_summaries = [
            SectorRegressionSummary.model_validate(result)
            for result in safe_regressions
        ]
    except ValidationError as error:
        raise QuantPipelineError(
            "sector regression schema validation failed"
        ) from error
    valid_sector_count = sum(result.status == "success" for result in sector_summaries)
    if valid_sector_count == 0:
        raise QuantPipelineError("no usable sector regressions were produced")

    safe_breadth = _json_safe(breadth_snapshot)
    safe_trend = _json_safe(trend_snapshot)
    data_sources = DataSources(
        price_provider=_combined_provider(
            [
                acquisition_context.equities,
                acquisition_context.spy,
                acquisition_context.sectors,
            ]
        ),
        treasury_provider=acquisition_context.treasury.provider,
        universe_provider=acquisition_context.universe.provider,
    )
    run_metadata = RunMetadata(
        run_id=resolved_run_id,
        as_of_date=common_as_of.date(),
        generated_at=resolved_generated_at,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        regression_window=config.analysis.regression_window,
        min_regression_obs=config.analysis.min_regression_obs,
        moving_average_windows=config.analysis.moving_average_windows,
        yield_unit=config.data.yield_unit,
        data_sources=data_sources,
    )
    try:
        breadth_summary = _json_safe(safe_breadth)
        trend_summary = _json_safe(safe_trend)
        data_quality = _build_data_quality(
            equity_prices=equity_prices,
            spy_observation_count=len(trend_timeseries),
            sector_prices=sector_prices,
            treasury_yields=treasury_yields,
            breadth=breadth_summary,
            sector_results=sector_summaries,
            context=acquisition_context,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        has_noncritical_gap = (
            valid_sector_count != len(sector_summaries)
            or breadth_summary["status"] == BreadthStatus.INSUFFICIENT_DATA
        )
        return QuantSummary(
            schema_version=SCHEMA_VERSION,
            run_metadata=run_metadata,
            data_quality=data_quality,
            breadth=breadth_summary,
            trend=trend_summary,
            sector_regressions=sector_summaries,
            limitations=_build_limitations(acquisition_context),
            status=(
                QuantStatus.PARTIAL if has_noncritical_gap else QuantStatus.SUCCESS
            ),
        )
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        raise QuantPipelineError("quant summary schema validation failed") from error


def serialize_quant_summary(summary: QuantSummary) -> str:
    """Serialize strict standards-compliant JSON with deterministic key order."""

    payload = summary.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_quant_summary(summary: QuantSummary, output_directory: str | Path) -> Path:
    """Atomically write outputs/<run_id>/quant_summary.json."""

    payload = serialize_quant_summary(summary)
    run_directory = Path(output_directory) / summary.run_metadata.run_id
    destination = run_directory / "quant_summary.json"
    temporary = run_directory / ".quant_summary.json.tmp"
    try:
        run_directory.mkdir(parents=True, exist_ok=True)
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(destination)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise QuantPipelineError(
            f"unable to write quant summary: {destination}"
        ) from error
    return destination
