"""Deterministic tests for the v1.1 web presentation adapter."""

from __future__ import annotations

import ast
import copy
import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.schemas import QuantSummary
from src.web_export import (
    BREADTH_FILENAME,
    MANIFEST_FILENAME,
    MARKET_FILENAME,
    PDF_FILENAME,
    QUANT_FILENAME,
    TREND_FILENAME,
    WebExportError,
    export_web_snapshot,
)
from tests.test_reporting import _available_interpretation, _summary
from tests.test_schemas import valid_summary_payload

WEB_EXPORT_SOURCE = Path(__file__).resolve().parents[1] / "src" / "web_export.py"
AS_OF = date(2023, 12, 29)


def _breadth_frame(*, as_of: date = AS_OF) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [as_of.replace(day=28), as_of],
            "pct_above_50dma": [70.0, 66.67],
            "pct_above_200dma": [np.nan, 66.67],
            "advancers": [2, 2],
            "decliners": [1, 1],
            "advance_decline_ratio": [2.0, 2.0],
            "net_advances": [1, 1],
            "breadth_momentum_20d": [np.nan, 0.0],
        }
    )


def _trend_frame(*, as_of: date = AS_OF) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [as_of.replace(day=28), as_of],
            "adjusted_close": [470.0, 475.0],
            "sma_20": [np.nan, 470.0],
            "sma_50": [np.nan, 460.0],
            "sma_200": [np.nan, 430.0],
            "trend_regime": ["insufficient_data", "strong_uptrend"],
        }
    )


def _export(tmp_path: Path, **overrides: object):
    summary = overrides["summary"] if "summary" in overrides else _summary()
    interpretation = (
        overrides["interpretation"]
        if "interpretation" in overrides
        else _available_interpretation(summary)
    )
    breadth = overrides["breadth"] if "breadth" in overrides else _breadth_frame()
    trend = overrides["trend"] if "trend" in overrides else _trend_frame()
    target = overrides["target"] if "target" in overrides else tmp_path / "web-data"
    return export_web_snapshot(summary, interpretation, breadth, trend, target)


def _load(target: Path, name: str) -> dict[str, object]:
    return json.loads((target / name).read_text(encoding="utf-8"))


def test_export_creates_required_artifacts(tmp_path: Path) -> None:
    result = _export(tmp_path)
    target = result.target_dir

    assert result.run_id == "fixed-run"
    assert result.as_of_date == AS_OF
    assert set(result.artifacts) == {
        QUANT_FILENAME,
        MARKET_FILENAME,
        BREADTH_FILENAME,
        TREND_FILENAME,
        MANIFEST_FILENAME,
    }
    for name in result.artifacts:
        assert (target / name).is_file()
        payload = _load(target, name)
        encoded = json.dumps(payload, allow_nan=False)
        assert "NaN" not in encoded
        assert "Infinity" not in encoded


def test_manifest_contract_and_filenames(tmp_path: Path) -> None:
    result = _export(tmp_path)
    manifest = _load(result.target_dir, MANIFEST_FILENAME)

    assert manifest == {
        "schema_version": "1.0.0",
        "run_id": "fixed-run",
        "as_of_date": "2023-12-29",
        "generated_at": "2024-01-02T12:00:00Z",
        "quant_status": "success",
        "interpretation_status": "available",
        "artifacts": {
            "quant_summary": QUANT_FILENAME,
            "market_summary": MARKET_FILENAME,
            "breadth_timeseries": BREADTH_FILENAME,
            "trend_timeseries": TREND_FILENAME,
        },
    }


def test_optional_pdf_is_copied_without_changing_json_contract(tmp_path: Path) -> None:
    pdf_source = tmp_path / "source.pdf"
    pdf_source.write_bytes(b"%PDF-1.4 test")
    exported = export_web_snapshot(
        _summary(),
        _available_interpretation(_summary()),
        _breadth_frame(),
        _trend_frame(),
        tmp_path / "web-with-pdf",
        pdf_path=pdf_source,
    )
    assert (exported.target_dir / PDF_FILENAME).read_bytes().startswith(b"%PDF")
    manifest = _load(exported.target_dir, MANIFEST_FILENAME)
    assert "market_report_pdf" not in manifest["artifacts"]


def test_run_id_and_as_of_are_consistent(tmp_path: Path) -> None:
    result = _export(tmp_path)
    target = result.target_dir
    documents = [
        _load(target, name)
        for name in (
            MANIFEST_FILENAME,
            QUANT_FILENAME,
            MARKET_FILENAME,
            BREADTH_FILENAME,
            TREND_FILENAME,
        )
    ]

    run_ids = {
        document.get("run_id") or document["run_metadata"]["run_id"]
        for document in documents
    }
    as_of_dates = {
        document.get("as_of_date") or document["run_metadata"]["as_of_date"]
        for document in documents
    }
    assert run_ids == {"fixed-run"}
    assert as_of_dates == {"2023-12-29"}


def test_unavailable_values_are_json_null(tmp_path: Path) -> None:
    result = _export(tmp_path)
    breadth = _load(result.target_dir, BREADTH_FILENAME)["series"]
    trend = _load(result.target_dir, TREND_FILENAME)["series"]

    assert breadth[0]["pct_above_200dma"] is None
    assert breadth[0]["breadth_momentum_20d"] is None
    assert trend[0]["sma_20"] is None
    assert trend[0]["sma_50"] is None
    assert trend[0]["sma_200"] is None
    assert breadth[1]["pct_above_50dma"] == 66.67
    assert trend[1]["sma_20"] == 470.0


def test_exported_series_match_source_frames(tmp_path: Path) -> None:
    breadth = _breadth_frame()
    trend = _trend_frame()
    result = _export(tmp_path, breadth=breadth, trend=trend)
    exported_breadth = _load(result.target_dir, BREADTH_FILENAME)["series"]
    exported_trend = _load(result.target_dir, TREND_FILENAME)["series"]

    assert len(exported_breadth) == len(breadth)
    assert len(exported_trend) == len(trend)
    source_breadth = breadth.sort_values("date", ignore_index=True)
    for exported, (_, source) in zip(
        exported_breadth, source_breadth.iterrows(), strict=True
    ):
        for column in (
            "pct_above_50dma",
            "pct_above_200dma",
            "advancers",
            "decliners",
            "advance_decline_ratio",
            "net_advances",
            "breadth_momentum_20d",
        ):
            expected = source[column]
            if pd.isna(expected):
                assert exported[column] is None
            else:
                assert exported[column] == pytest.approx(expected)
    assert exported_trend[1]["adjusted_close"] == pytest.approx(475.0)
    assert exported_trend[1]["sma_20"] == pytest.approx(470.0)
    assert exported_trend[1]["trend_regime"] == "strong_uptrend"
    assert exported_trend[0]["sma_200"] is None
    assert all(math.isfinite(row["adjusted_close"]) for row in exported_trend)


def test_exporter_source_does_not_compute_or_call_openai() -> None:
    source = WEB_EXPORT_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)

    forbidden_modules = {
        "openai",
        "src.breadth",
        "src.trend",
        "src.regression",
        "src.data_loader",
    }
    assert imported.isdisjoint(forbidden_modules)
    assert called.isdisjoint(
        {
            "compute_breadth_timeseries",
            "compute_trend_timeseries",
            "run_sector_regressions",
            "interpret_quant_summary",
        }
    )


def test_mismatched_run_id_fails(tmp_path: Path) -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary).model_copy(
        update={"run_id": "other-run"}
    )

    with pytest.raises(WebExportError, match="run_id mismatch"):
        export_web_snapshot(
            summary,
            interpretation,
            _breadth_frame(),
            _trend_frame(),
            tmp_path / "web-data",
        )
    assert not (tmp_path / "web-data" / MANIFEST_FILENAME).exists()


def test_mismatched_as_of_date_fails(tmp_path: Path) -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary).model_copy(
        update={"as_of_date": date(2023, 1, 2)}
    )

    with pytest.raises(WebExportError, match="as_of_date mismatch"):
        export_web_snapshot(
            summary,
            interpretation,
            _breadth_frame(),
            _trend_frame(),
            tmp_path / "web-data",
        )


def test_incompatible_series_date_fails(tmp_path: Path) -> None:
    with pytest.raises(WebExportError, match="breadth latest date"):
        export_web_snapshot(
            _summary(),
            _available_interpretation(_summary()),
            _breadth_frame(as_of=date(2023, 12, 15)),
            _trend_frame(),
            tmp_path / "web-data",
        )


def test_empty_series_fails(tmp_path: Path) -> None:
    empty = _breadth_frame().iloc[0:0]
    with pytest.raises(WebExportError, match="must not be empty"):
        export_web_snapshot(
            _summary(),
            _available_interpretation(_summary()),
            empty,
            _trend_frame(),
            tmp_path / "web-data",
        )


def test_infinite_series_value_fails(tmp_path: Path) -> None:
    trend = _trend_frame()
    trend.loc[trend.index[-1], "adjusted_close"] = math.inf
    with pytest.raises(WebExportError, match="Infinity"):
        export_web_snapshot(
            _summary(),
            _available_interpretation(_summary()),
            _breadth_frame(),
            trend,
            tmp_path / "web-data",
        )


def test_malformed_series_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(WebExportError, match="missing columns"):
        export_web_snapshot(
            _summary(),
            _available_interpretation(_summary()),
            pd.DataFrame({"date": [AS_OF]}),
            _trend_frame(),
            tmp_path / "web-data",
        )


def test_atomic_write_failure_preserves_previous_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "web-data"
    first = _export(tmp_path, target=target)
    original = {
        name: path.read_text(encoding="utf-8") for name, path in first.artifacts.items()
    }

    def fail_replace(self: Path, destination: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)
    payload = copy.deepcopy(valid_summary_payload())
    payload["run_metadata"]["run_id"] = "second-run"
    second_summary = QuantSummary.model_validate(payload)
    second_interpretation = _available_interpretation(second_summary)

    with pytest.raises(WebExportError, match="unable to write"):
        export_web_snapshot(
            second_summary,
            second_interpretation,
            _breadth_frame(),
            _trend_frame(),
            target,
        )

    for name, text in original.items():
        assert (target / name).read_text(encoding="utf-8") == text
        assert not (target / f".{name}.tmp").exists()
    assert "second-run" not in (target / MANIFEST_FILENAME).read_text(encoding="utf-8")


def test_export_is_deterministic(tmp_path: Path) -> None:
    first = _export(tmp_path, target=tmp_path / "one")
    second = _export(tmp_path, target=tmp_path / "two")

    for name in first.artifacts:
        assert (first.target_dir / name).read_text(encoding="utf-8") == (
            second.target_dir / name
        ).read_text(encoding="utf-8")
