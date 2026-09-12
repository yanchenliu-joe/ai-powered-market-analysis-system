"""Serialize-only live-run bundle tests. No indicator recomputation."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd
import pytest

from src.run_bundle import RunBundleError, export_run_bundle
from src.web_export import (
    BREADTH_FILENAME,
    MARKET_FILENAME,
    PDF_FILENAME,
    QUANT_FILENAME,
    TREND_FILENAME,
)
from tests.test_reporting import _available_interpretation, _summary
from tests.test_web_export import _breadth_frame, _trend_frame

BUNDLE_SOURCE = Path(__file__).resolve().parents[1] / "src" / "run_bundle.py"
PIPELINE_SOURCE = Path(__file__).resolve().parents[1] / "src" / "pipeline.py"


def _export(tmp_path: Path, **overrides: object):
    summary = overrides["summary"] if "summary" in overrides else _summary()
    interpretation = (
        overrides["interpretation"]
        if "interpretation" in overrides
        else _available_interpretation(summary)
    )
    breadth = overrides["breadth"] if "breadth" in overrides else _breadth_frame()
    trend = overrides["trend"] if "trend" in overrides else _trend_frame()
    target = overrides["target"] if "target" in overrides else tmp_path / "bundle"
    return export_run_bundle(
        summary,
        interpretation,
        breadth,
        trend,
        target,
        pdf_path=overrides.get("pdf_path"),
        source_directory=overrides.get("source_directory"),
    )


def test_bundle_receives_precomputed_series(tmp_path: Path) -> None:
    breadth = _breadth_frame()
    trend = _trend_frame()
    result = _export(tmp_path, breadth=breadth, trend=trend)
    exported = json.loads((result.target_dir / BREADTH_FILENAME).read_text())
    assert exported["series"][1]["pct_above_50dma"] == pytest.approx(66.67)
    trend_doc = json.loads((result.target_dir / TREND_FILENAME).read_text())
    assert trend_doc["series"][1]["adjusted_close"] == pytest.approx(475.0)
    assert trend_doc["series"] is not breadth


def test_required_bundle_artifacts_are_produced(tmp_path: Path) -> None:
    pdf = tmp_path / "market_report.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    result = _export(tmp_path, pdf_path=pdf)
    for name in (
        QUANT_FILENAME,
        MARKET_FILENAME,
        BREADTH_FILENAME,
        TREND_FILENAME,
        PDF_FILENAME,
    ):
        assert (result.target_dir / name).is_file()


def test_bundle_does_not_write_public_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    public = tmp_path / "web" / "public" / "data"
    public.mkdir(parents=True)
    with pytest.raises(RunBundleError, match="web/public/data"):
        _export(tmp_path, target=public)


def test_no_indicator_recomputation_in_run_bundle() -> None:
    tree = ast.parse(BUNDLE_SOURCE.read_text(encoding="utf-8"))
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    forbidden = {
        "compute_breadth",
        "compute_trend",
        "rolling",
        "pct_change",
        "ols",
        "fit",
    }
    assert forbidden.isdisjoint(calls)
    source = BUNDLE_SOURCE.read_text(encoding="utf-8")
    assert "serialize_quant_summary" in source
    assert "web/public/data" in source


def test_pipeline_live_hook_does_not_use_web_snapshot_dir() -> None:
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")
    assert "export_run_bundle" in source
    assert 'run_directory / "bundle"' in source or "run_directory / 'bundle'" in source


def test_no_secrets_written_into_bundle(tmp_path: Path) -> None:
    result = _export(tmp_path)
    for path in result.target_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" not in text
        assert "BLOB_READ_WRITE_TOKEN" not in text
        assert "RUN_ANALYSIS_SECRET" not in text


def test_missing_pdf_is_honest(tmp_path: Path) -> None:
    with pytest.raises(RunBundleError, match="PDF"):
        _export(tmp_path, pdf_path=tmp_path / "missing.pdf")


def test_optional_source_copies(tmp_path: Path) -> None:
    source = tmp_path / "run"
    source.mkdir()
    (source / "market_report.md").write_text("# report\n")
    (source / "spy_trend.png").write_bytes(b"png")
    result = _export(tmp_path, source_directory=source)
    assert (result.target_dir / "market_report.md").is_file()
    assert (result.target_dir / "spy_trend.png").is_file()


def test_export_does_not_mutate_source_frames(tmp_path: Path) -> None:
    breadth = _breadth_frame()
    original = breadth.copy()
    _export(tmp_path, breadth=breadth)
    pd.testing.assert_frame_equal(breadth, original)
