"""End-to-end orchestration of accepted Phase 2–9 modules."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.breadth import compute_breadth_timeseries
from src.config import PROJECT_ROOT, AppConfig
from src.data_loader import (
    DataLoaderError,
    PriceProvider,
    UniverseProvider,
    YieldProvider,
    load_dgs10,
    load_equity_prices,
    load_sector_prices,
    load_sp500_universe,
    load_spy_prices,
    resolve_default_date_range,
)
from src.fixture_data import (
    FIXTURE_RUN_ID,
    fixture_dates_for_config,
    fixture_price_provider,
    fixture_universe_provider,
    fixture_yield_provider,
)
from src.interpretation import CompleteFn, interpret_quant_summary
from src.pdf_report import PdfReportError, generate_pdf_report
from src.preprocessing import DataValidationError
from src.quant_pipeline import (
    AcquisitionContext,
    QuantPipelineError,
    run_quant_pipeline,
    write_quant_summary,
)
from src.reporting import ReportError, generate_report
from src.run_bundle import RunBundleError, export_run_bundle
from src.schemas import InterpretationStatus, MarketInterpretation, QuantSummary
from src.trend import compute_trend_timeseries
from src.visualization import VisualizationError, generate_all_visualizations
from src.web_export import WebExportError, export_web_snapshot

LOGGER = logging.getLogger(__name__)

SUCCESS = 0
FAILURE = 1
PARTIAL = 2


@dataclass
class RunOptions:
    run_id: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    force_refresh: bool = False
    skip_openai: bool = False
    fixture: bool = False
    generated_at: datetime | None = None
    interpret_complete: CompleteFn | None = None
    universe_provider: UniverseProvider | None = None
    price_provider: PriceProvider | None = None
    yield_provider: YieldProvider | None = None
    export_web_snapshot: bool = False
    web_snapshot_directory: Path | None = None
    export_run_bundle: bool = False
    run_bundle_directory: Path | None = None


@dataclass
class RunResult:
    exit_code: int
    run_id: str
    run_directory: Path
    summary: QuantSummary | None = None
    interpretation: MarketInterpretation | None = None
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, Path] = field(default_factory=dict)


def _log(run_id: str, stage: str, status: str, message: str, **duration: Any) -> None:
    extra = {"run_id": run_id, "stage": stage, "status": status}
    if duration:
        message = f"{message} duration_ms={duration.get('duration_ms')}"
    LOGGER.info(message, extra=extra)


def execute_analysis(config: AppConfig, options: RunOptions | None = None) -> RunResult:
    """Run the accepted quantitative, visualization, interpretation, and report path."""

    options = options or RunOptions()
    fixture = options.fixture
    run_id = options.run_id or (FIXTURE_RUN_ID if fixture else uuid4().hex)
    generated_at = options.generated_at or datetime.now(UTC)
    if fixture:
        start, end = fixture_dates_for_config(config)
        if options.start_date is not None:
            start = options.start_date
        if options.end_date is not None:
            end = options.end_date
        universe_provider = options.universe_provider or fixture_universe_provider
        price_provider = options.price_provider or fixture_price_provider
        yield_provider = options.yield_provider or fixture_yield_provider
        skip_openai = (
            True if options.interpret_complete is None else options.skip_openai
        )
    else:
        default_start, default_end = resolve_default_date_range()
        start = options.start_date or default_start
        end = options.end_date or default_end
        universe_provider = options.universe_provider
        price_provider = options.price_provider
        yield_provider = options.yield_provider
        skip_openai = options.skip_openai

    cache_directory = config.data.raw_directory
    if fixture:
        cache_directory = config.data.raw_directory / "_fixture"
    output_directory = config.output.directory
    run_directory = output_directory / run_id
    warnings: list[str] = []
    _log(
        run_id,
        "startup",
        "started",
        f"analysis {start.isoformat()} to {end.isoformat()}",
    )

    try:
        stage_started = time.perf_counter()
        universe = load_sp500_universe(
            cache_directory=cache_directory,
            force_refresh=options.force_refresh,
            provider=universe_provider,
        )
        tickers = universe.data["ticker"].tolist()
        equities = load_equity_prices(
            tickers,
            start,
            end,
            cache_directory=cache_directory,
            force_refresh=options.force_refresh,
            provider=price_provider,
        )
        spy = load_spy_prices(
            start,
            end,
            ticker=config.data.benchmark_ticker,
            cache_directory=cache_directory,
            force_refresh=options.force_refresh,
            provider=price_provider,
        )
        sectors = load_sector_prices(
            list(config.data.sector_tickers),
            start,
            end,
            cache_directory=cache_directory,
            force_refresh=options.force_refresh,
            provider=price_provider,
        )
        treasury = load_dgs10(
            start,
            end,
            series=config.data.treasury_series,
            cache_directory=cache_directory,
            force_refresh=options.force_refresh,
            provider=yield_provider,
        )
        _log(
            run_id,
            "data",
            "success",
            "canonical datasets loaded",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    except (DataLoaderError, DataValidationError, ValueError) as error:
        _log(run_id, "data", "failure", str(error))
        return RunResult(FAILURE, run_id, run_directory, warnings=warnings)

    try:
        stage_started = time.perf_counter()
        summary = run_quant_pipeline(
            equities.data,
            spy.data,
            sectors.data,
            treasury.data,
            config=config,
            acquisition_context=AcquisitionContext(
                universe=universe.metadata,
                equities=equities.metadata,
                spy=spy.metadata,
                sectors=sectors.metadata,
                treasury=treasury.metadata,
            ),
            analysis_start=start,
            analysis_end=end,
            run_id=run_id,
            generated_at=generated_at,
        )
        quant_path = write_quant_summary(summary, output_directory)
        breadth_timeseries = compute_breadth_timeseries(equities.data)
        trend_timeseries = compute_trend_timeseries(spy.data)
        _log(
            run_id,
            "quant",
            summary.status.value,
            "quant_summary.json written",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    except QuantPipelineError as error:
        _log(run_id, "quant", "failure", str(error))
        return RunResult(FAILURE, run_id, run_directory, warnings=warnings)

    artifacts = {"quant_summary.json": quant_path}
    try:
        stage_started = time.perf_counter()
        charts = generate_all_visualizations(
            breadth_timeseries,
            trend_timeseries,
            summary,
            output_directory,
        )
        for chart in charts:
            artifacts[chart.output_path.name] = chart.output_path
        _log(
            run_id,
            "visualization",
            "success",
            "chart artifacts written",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    except VisualizationError as error:
        warning = f"visualization failed: {error}"
        warnings.append(warning)
        _log(run_id, "visualization", "partial", warning)

    stage_started = time.perf_counter()
    interpretation = interpret_quant_summary(
        summary,
        output_directory=output_directory,
        model=config.llm.model,
        complete=options.interpret_complete,
        generated_at=generated_at,
        skip=skip_openai,
    )
    artifacts["market_summary.json"] = output_directory / run_id / "market_summary.json"
    _log(
        run_id,
        "interpretation",
        interpretation.status.value,
        interpretation.reason or "available",
        duration_ms=int((time.perf_counter() - stage_started) * 1000),
    )

    try:
        stage_started = time.perf_counter()
        report = generate_report(
            summary, interpretation, output_directory=output_directory
        )
        artifacts["market_report.md"] = report.path
        _log(
            run_id,
            "report",
            "success",
            "market_report.md written",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    except ReportError as error:
        _log(run_id, "report", "failure", str(error))
        return RunResult(
            FAILURE,
            run_id,
            run_directory,
            summary=summary,
            interpretation=interpretation,
            warnings=warnings,
            artifacts=artifacts,
        )

    try:
        stage_started = time.perf_counter()
        pdf = generate_pdf_report(
            summary, interpretation, output_directory=output_directory
        )
        artifacts["market_report.pdf"] = pdf.path
        _log(
            run_id,
            "pdf_report",
            "success",
            "market_report.pdf written",
            duration_ms=int((time.perf_counter() - stage_started) * 1000),
        )
    except PdfReportError as error:
        warning = f"PDF report generation failed: {error}"
        warnings.append(warning)
        _log(run_id, "pdf_report", "partial", warning)

    if options.export_web_snapshot:
        target = options.web_snapshot_directory or (
            PROJECT_ROOT / "web" / "public" / "data"
        )
        try:
            stage_started = time.perf_counter()
            exported = export_web_snapshot(
                summary,
                interpretation,
                breadth_timeseries,
                trend_timeseries,
                target,
                pdf_path=artifacts.get("market_report.pdf"),
            )
            artifacts["web_snapshot"] = exported.target_dir
            _log(
                run_id,
                "web_export",
                "success",
                f"web snapshot written to {exported.target_dir}",
                duration_ms=int((time.perf_counter() - stage_started) * 1000),
            )
        except WebExportError as error:
            warning = f"web snapshot export failed: {error}"
            warnings.append(warning)
            _log(run_id, "web_export", "partial", warning)

    if options.export_run_bundle:
        target = options.run_bundle_directory or (run_directory / "bundle")
        try:
            stage_started = time.perf_counter()
            bundled = export_run_bundle(
                summary,
                interpretation,
                breadth_timeseries,
                trend_timeseries,
                target,
                pdf_path=artifacts.get("market_report.pdf"),
                source_directory=run_directory,
            )
            artifacts["run_bundle"] = bundled.target_dir
            _log(
                run_id,
                "run_bundle",
                "success",
                f"run bundle written to {bundled.target_dir}",
                duration_ms=int((time.perf_counter() - stage_started) * 1000),
            )
        except RunBundleError as error:
            warning = f"run bundle export failed: {error}"
            warnings.append(warning)
            _log(run_id, "run_bundle", "partial", warning)

    missing_charts = [
        name
        for name in (
            "breadth_timeseries.png",
            "spy_trend.png",
            "sector_rate_beta.png",
        )
        if name not in artifacts
    ]
    degraded = (
        interpretation.status is InterpretationStatus.UNAVAILABLE
        or bool(warnings)
        or bool(missing_charts)
        or summary.status.value == "partial"
    )
    exit_code = PARTIAL if degraded else SUCCESS
    _log(run_id, "complete", "partial" if degraded else "success", "run finished")
    return RunResult(
        exit_code,
        run_id,
        run_directory,
        summary=summary,
        interpretation=interpretation,
        warnings=warnings,
        artifacts=artifacts,
    )
