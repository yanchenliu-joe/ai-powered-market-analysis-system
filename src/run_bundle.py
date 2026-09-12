"""Serialize a temporary live-run bundle from already-validated artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from shutil import copy2

import pandas as pd

from src.interpretation import serialize_market_interpretation
from src.quant_pipeline import serialize_quant_summary
from src.schemas import MarketInterpretation, QuantSummary
from src.web_export import (
    BREADTH_FILENAME,
    BREADTH_SERIES_FIELDS,
    MARKET_FILENAME,
    PDF_FILENAME,
    QUANT_FILENAME,
    TREND_FILENAME,
    TREND_SERIES_FIELDS,
    WebExportError,
    _dumps,
    _normalize_series,
    _series_document,
    _validate_consistency,
    _write_atomic_files,
)

OPTIONAL_FILES = (
    "market_report.md",
    "breadth_timeseries.png",
    "spy_trend.png",
    "sector_rate_beta.png",
)


class RunBundleError(WebExportError):
    """Raised when a live-run bundle cannot be written."""


@dataclass(frozen=True)
class RunBundleResult:
    run_id: str
    as_of_date: date
    target_dir: Path
    artifacts: dict[str, Path]


def export_run_bundle(
    summary: QuantSummary,
    interpretation: MarketInterpretation,
    breadth_timeseries: pd.DataFrame,
    trend_timeseries: pd.DataFrame,
    target_directory: str | Path,
    *,
    pdf_path: str | Path | None = None,
    source_directory: str | Path | None = None,
) -> RunBundleResult:
    """Write one run-scoped presentation bundle. Never writes web/public/data."""

    target = Path(target_directory).resolve()
    public_data = (Path.cwd() / "web" / "public" / "data").resolve()
    if target == public_data or public_data in target.parents:
        raise RunBundleError("live run bundle must not write web/public/data")

    breadth = _normalize_series(
        breadth_timeseries, BREADTH_SERIES_FIELDS, label="breadth"
    )
    trend = _normalize_series(trend_timeseries, TREND_SERIES_FIELDS, label="trend")
    _validate_consistency(summary, interpretation, breadth, trend)

    files = {
        QUANT_FILENAME: serialize_quant_summary(summary),
        MARKET_FILENAME: serialize_market_interpretation(interpretation),
        BREADTH_FILENAME: _dumps(
            _series_document(summary, breadth, BREADTH_SERIES_FIELDS)
        ),
        TREND_FILENAME: _dumps(_series_document(summary, trend, TREND_SERIES_FIELDS)),
    }
    try:
        artifacts = _write_atomic_files(files, target)
    except WebExportError as error:
        raise RunBundleError(str(error)) from error

    if pdf_path is not None:
        source = Path(pdf_path)
        if not source.is_file():
            raise RunBundleError(f"PDF artifact is missing: {source}")
        destination = target / PDF_FILENAME
        copy2(source, destination)
        artifacts[PDF_FILENAME] = destination

    if source_directory is not None:
        origin = Path(source_directory)
        for name in OPTIONAL_FILES:
            candidate = origin / name
            if candidate.is_file():
                destination = target / name
                copy2(candidate, destination)
                artifacts[name] = destination

    return RunBundleResult(
        run_id=summary.run_metadata.run_id,
        as_of_date=summary.run_metadata.as_of_date,
        target_dir=target,
        artifacts=artifacts,
    )
