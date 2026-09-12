"""Deterministic tests for pipeline PDF assembly."""

from __future__ import annotations

import ast
from pathlib import Path

from reportlab.platypus import Paragraph

from src.interpretation import serialize_market_interpretation
from src.pdf_report import (
    PDF_FILENAME,
    _build_story,
    _styles,
    generate_pdf_from_run_directory,
    generate_pdf_report,
)
from src.quant_pipeline import write_quant_summary
from src.reporting import generate_report
from tests.test_reporting import _available_interpretation, _eleven_sector_summary

PDF_SOURCE = Path(__file__).resolve().parents[1] / "src" / "pdf_report.py"


def test_pdf_module_does_not_recompute_analytics() -> None:
    tree = ast.parse(PDF_SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
    assert "src.breadth" not in imported
    assert "src.trend" not in imported
    assert "src.regression" not in imported
    assert "src.llm_analyzer" not in imported
    assert "openai" not in imported
    assert "yfinance" not in imported


def test_generate_pdf_writes_professional_artifact(tmp_path: Path) -> None:
    summary = _eleven_sector_summary()
    interpretation = _available_interpretation(summary)
    run_dir = tmp_path / summary.run_metadata.run_id
    run_dir.mkdir()
    from PIL import Image as PillowImage

    for name in ("breadth_timeseries.png", "spy_trend.png", "sector_rate_beta.png"):
        PillowImage.new("RGB", (32, 24), (230, 226, 214)).save(run_dir / name)
    generate_report(summary, interpretation, output_directory=tmp_path)
    artifact = generate_pdf_report(summary, interpretation, output_directory=tmp_path)
    payload = artifact.path.read_bytes()
    assert artifact.path.name == PDF_FILENAME
    assert payload.startswith(b"%PDF")
    assert artifact.included_charts == (
        "breadth_timeseries.png",
        "spy_trend.png",
        "sector_rate_beta.png",
    )
    story, _included = _build_story(summary, interpretation, run_dir, _styles())
    text = " ".join(item.text for item in story if isinstance(item, Paragraph))
    for heading in (
        "Executive Summary",
        "Market Participation",
        "Trend Conditions",
        "Sector Rate Sensitivity",
        "Data Quality",
        "Methodology and Limitations",
        "Disclaimer",
        summary.run_metadata.run_id,
        summary.run_metadata.as_of_date.isoformat(),
        "EXEC_SUMMARY_PROSE",
    ):
        assert heading in text


def test_missing_charts_do_not_block_pdf(tmp_path: Path) -> None:
    summary = _eleven_sector_summary()
    interpretation = _available_interpretation(summary)
    artifact = generate_pdf_report(summary, interpretation, output_directory=tmp_path)
    assert artifact.included_charts == ()
    assert artifact.path.is_file()
    assert b"%PDF" in artifact.path.read_bytes()[:8]


def test_generate_pdf_from_existing_json(tmp_path: Path) -> None:
    summary = _eleven_sector_summary()
    interpretation = _available_interpretation(summary)
    run_dir = tmp_path / summary.run_metadata.run_id
    write_quant_summary(summary, tmp_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "market_summary.json").write_text(
        serialize_market_interpretation(interpretation), encoding="utf-8"
    )
    generate_report(summary, interpretation, output_directory=tmp_path)
    artifact = generate_pdf_from_run_directory(run_dir)
    assert artifact.path.is_file()
    assert artifact.run_id == summary.run_metadata.run_id
