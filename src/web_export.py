"""Serialize accepted v1.0 results into a static web snapshot."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from shutil import copy2
from typing import Any
from uuid import uuid4

import pandas as pd

from src.interpretation import serialize_market_interpretation
from src.quant_pipeline import serialize_quant_summary
from src.schemas import MarketInterpretation, QuantSummary

WEB_SCHEMA_VERSION = "1.0.0"
MANIFEST_FILENAME = "snapshot_manifest.json"
QUANT_FILENAME = "quant_summary.json"
MARKET_FILENAME = "market_summary.json"
BREADTH_FILENAME = "breadth_timeseries.json"
TREND_FILENAME = "trend_timeseries.json"
PDF_FILENAME = "market_report.pdf"

BREADTH_SERIES_FIELDS = (
    "date",
    "pct_above_50dma",
    "pct_above_200dma",
    "advancers",
    "decliners",
    "advance_decline_ratio",
    "net_advances",
    "breadth_momentum_20d",
)
TREND_SERIES_FIELDS = (
    "date",
    "adjusted_close",
    "sma_20",
    "sma_50",
    "sma_200",
    "trend_regime",
)


class WebExportError(RuntimeError):
    """Raised when a web snapshot cannot be validated or written."""


@dataclass(frozen=True)
class WebExportResult:
    run_id: str
    as_of_date: date
    target_dir: Path
    artifacts: dict[str, Path]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if not math.isfinite(value):
            raise WebExportError("web snapshot contains Infinity")
    return value


def _dumps(payload: dict[str, Any]) -> str:
    return (
        json.dumps(
            _json_safe(payload),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _as_date(value: Any, *, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError) as error:
        raise WebExportError(f"{field_name} is not a valid date") from error


def _normalize_series(
    data: pd.DataFrame,
    required: tuple[str, ...],
    *,
    label: str,
) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise WebExportError(f"{label} series must be a DataFrame")
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise WebExportError(f"{label} series is missing columns: {', '.join(missing)}")
    if data.empty:
        raise WebExportError(f"{label} series must not be empty")
    frame = data.loc[:, list(required)].copy()
    try:
        converted = pd.to_datetime(frame["date"], errors="raise", utc=True)
        frame["date"] = converted.dt.tz_convert(None).dt.normalize()
    except (TypeError, ValueError) as error:
        raise WebExportError(f"{label} series dates are missing or invalid") from error
    if frame["date"].isna().any():
        raise WebExportError(f"{label} series dates are missing or invalid")
    if frame["date"].duplicated().any():
        raise WebExportError(f"{label} series contains duplicate dates")
    return frame.sort_values("date", ignore_index=True)


def _latest_date(frame: pd.DataFrame) -> date:
    return pd.Timestamp(frame["date"].iloc[-1]).date()


def _validate_consistency(
    summary: QuantSummary,
    interpretation: MarketInterpretation,
    breadth: pd.DataFrame,
    trend: pd.DataFrame,
) -> None:
    quant_run = summary.run_metadata.run_id
    quant_date = summary.run_metadata.as_of_date
    if interpretation.run_id != quant_run:
        raise WebExportError(
            f"run_id mismatch: quant={quant_run!r} interpretation="
            f"{interpretation.run_id!r}"
        )
    if interpretation.as_of_date != quant_date:
        raise WebExportError(
            f"as_of_date mismatch: quant={quant_date.isoformat()} "
            f"interpretation={interpretation.as_of_date.isoformat()}"
        )
    breadth_as_of = _latest_date(breadth)
    trend_as_of = _latest_date(trend)
    if breadth_as_of != quant_date:
        raise WebExportError(
            f"breadth latest date {breadth_as_of.isoformat()} is not compatible "
            f"with snapshot as_of_date {quant_date.isoformat()}"
        )
    if trend_as_of != quant_date:
        raise WebExportError(
            f"trend latest date {trend_as_of.isoformat()} is not compatible "
            f"with snapshot as_of_date {quant_date.isoformat()}"
        )


def _series_records(
    frame: pd.DataFrame, fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame.itertuples(index=False):
        values = dict(zip(frame.columns, row, strict=True))
        record: dict[str, Any] = {}
        for field in fields:
            value = values[field]
            if field == "date":
                record[field] = _as_date(value, field_name="date").isoformat()
            elif pd.isna(value):
                record[field] = None
            elif field == "trend_regime":
                record[field] = str(value)
            else:
                record[field] = _json_safe(value)
        records.append(record)
    return records


def _series_document(
    summary: QuantSummary,
    frame: pd.DataFrame,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_version": WEB_SCHEMA_VERSION,
        "run_id": summary.run_metadata.run_id,
        "as_of_date": summary.run_metadata.as_of_date.isoformat(),
        "series": _series_records(frame, fields),
    }


def _manifest_document(
    summary: QuantSummary, interpretation: MarketInterpretation
) -> dict[str, Any]:
    generated = summary.run_metadata.generated_at
    generated_at = generated.isoformat().replace("+00:00", "Z")
    return {
        "schema_version": WEB_SCHEMA_VERSION,
        "run_id": summary.run_metadata.run_id,
        "as_of_date": summary.run_metadata.as_of_date.isoformat(),
        "generated_at": generated_at,
        "quant_status": summary.status.value,
        "interpretation_status": interpretation.status.value,
        "artifacts": {
            "quant_summary": QUANT_FILENAME,
            "market_summary": MARKET_FILENAME,
            "breadth_timeseries": BREADTH_FILENAME,
            "trend_timeseries": TREND_FILENAME,
        },
    }


def _write_atomic_files(
    files: dict[str, str], target_directory: Path
) -> dict[str, Path]:
    target_directory.mkdir(parents=True, exist_ok=True)
    staging = target_directory / f".web_export_staging_{uuid4().hex}"
    written: dict[str, Path] = {}
    try:
        staging.mkdir(parents=True, exist_ok=False)
        for filename, payload in files.items():
            (staging / filename).write_text(payload, encoding="utf-8")
        for filename, payload in files.items():
            destination = target_directory / filename
            temporary = target_directory / f".{filename}.tmp"
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(destination)
            written[filename] = destination
    except OSError as error:
        for filename in files:
            temporary = target_directory / f".{filename}.tmp"
            temporary.unlink(missing_ok=True)
        raise WebExportError(
            f"unable to write web snapshot: {target_directory}"
        ) from error
    finally:
        if staging.exists():
            for leftover in staging.glob("*"):
                leftover.unlink(missing_ok=True)
            staging.rmdir()
    return written


def export_web_snapshot(
    summary: QuantSummary,
    interpretation: MarketInterpretation,
    breadth_timeseries: pd.DataFrame,
    trend_timeseries: pd.DataFrame,
    target_directory: str | Path,
    pdf_path: str | Path | None = None,
) -> WebExportResult:
    """Write one coherent static snapshot for the future web dashboard."""

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
        MANIFEST_FILENAME: _dumps(_manifest_document(summary, interpretation)),
    }
    target = Path(target_directory)
    artifacts = _write_atomic_files(files, target)
    if pdf_path is not None:
        source = Path(pdf_path)
        if not source.is_file():
            raise WebExportError(f"PDF artifact is missing: {source}")
        destination = target / PDF_FILENAME
        try:
            copy2(source, destination)
        except OSError as error:
            raise WebExportError(
                f"unable to copy PDF into web snapshot: {destination}"
            ) from error
        artifacts[PDF_FILENAME] = destination
    return WebExportResult(
        run_id=summary.run_metadata.run_id,
        as_of_date=summary.run_metadata.as_of_date,
        target_dir=target,
        artifacts=artifacts,
    )
