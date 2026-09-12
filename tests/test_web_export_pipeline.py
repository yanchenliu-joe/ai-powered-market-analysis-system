"""CLI and pipeline integration for explicit web snapshot export."""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.config import load_config
from src.main import ExitCode, build_parser, main
from src.pipeline import RunOptions, execute_analysis
from src.web_export import (
    BREADTH_FILENAME,
    MANIFEST_FILENAME,
    MARKET_FILENAME,
    QUANT_FILENAME,
    TREND_FILENAME,
    WebExportError,
    WebExportResult,
)
from tests.test_integration import _complete_from_messages

PIPELINE_SOURCE = Path(__file__).resolve().parents[1] / "src" / "pipeline.py"
SNAPSHOT_FILES = (
    MANIFEST_FILENAME,
    QUANT_FILENAME,
    MARKET_FILENAME,
    BREADTH_FILENAME,
    TREND_FILENAME,
)
FIXED_GENERATED_AT = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)


def _config(tmp_path: Path):
    config = load_config(load_env_file=False)
    config.data.raw_directory = tmp_path / "raw"
    config.output.directory = tmp_path / "outputs"
    config.data.raw_directory.mkdir()
    config.output.directory.mkdir()
    return config


def test_cli_export_web_snapshot_flag_is_accepted() -> None:
    help_text = build_parser().format_help()
    assert "--export-web-snapshot" in help_text
    parsed = build_parser().parse_args(
        ["--export-web-snapshot", "--web-snapshot-dir", "/tmp/web-data"]
    )
    assert parsed.export_web_snapshot is True
    assert parsed.web_snapshot_dir == Path("/tmp/web-data")


def test_export_flag_reaches_export_web_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_export(summary, interpretation, breadth, trend, target, pdf_path=None):
        captured["summary"] = summary
        captured["interpretation"] = interpretation
        captured["breadth"] = breadth
        captured["trend"] = trend
        captured["pdf_path"] = pdf_path
        captured["target"] = Path(target)
        return WebExportResult(
            run_id=summary.run_metadata.run_id,
            as_of_date=summary.run_metadata.as_of_date,
            target_dir=Path(target),
            artifacts={},
        )

    monkeypatch.setattr("src.pipeline.export_web_snapshot", fake_export)
    web_dir = tmp_path / "web-data"
    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=True,
            run_id="export-flag",
            generated_at=FIXED_GENERATED_AT,
            export_web_snapshot=True,
            web_snapshot_directory=web_dir,
        ),
    )
    assert result.exit_code == ExitCode.PARTIAL
    assert captured["target"] == web_dir
    assert captured["summary"] is result.summary
    assert captured["interpretation"] is result.interpretation


def test_normal_cli_without_flag_does_not_modify_web_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {"value": False}

    def fake_export(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("export_web_snapshot must not run without the flag")

    monkeypatch.setattr("src.pipeline.export_web_snapshot", fake_export)
    sentinel = tmp_path / "web-data"
    sentinel.mkdir()
    marker = sentinel / "do-not-touch.txt"
    marker.write_text("keep", encoding="utf-8")

    code = main(
        [
            "--fixture",
            "--skip-openai",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "no-web-export",
            "--web-snapshot-dir",
            str(sentinel),
        ]
    )
    assert code == ExitCode.PARTIAL
    assert called["value"] is False
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not (sentinel / QUANT_FILENAME).exists()


def test_exporter_receives_precomputed_timeseries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, pd.DataFrame] = {}

    def fake_export(summary, interpretation, breadth, trend, target, pdf_path=None):
        captured["breadth"] = breadth
        captured["trend"] = trend
        return WebExportResult(
            run_id=summary.run_metadata.run_id,
            as_of_date=summary.run_metadata.as_of_date,
            target_dir=Path(target),
            artifacts={},
        )

    monkeypatch.setattr("src.pipeline.export_web_snapshot", fake_export)
    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=True,
            run_id="precomputed-frames",
            generated_at=FIXED_GENERATED_AT,
            export_web_snapshot=True,
            web_snapshot_directory=tmp_path / "web-data",
        ),
    )
    as_of = result.summary.run_metadata.as_of_date
    breadth = captured["breadth"]
    trend = captured["trend"]
    assert isinstance(breadth, pd.DataFrame)
    assert isinstance(trend, pd.DataFrame)
    assert "pct_above_50dma" in breadth.columns
    assert "pct_above_200dma" in breadth.columns
    assert "adjusted_close" in trend.columns
    assert {"sma_20", "sma_50", "sma_200"}.issubset(trend.columns)
    assert pd.Timestamp(breadth["date"].iloc[-1]).date() == as_of
    assert pd.Timestamp(trend["date"].iloc[-1]).date() == as_of


def test_pipeline_export_does_not_recompute_series() -> None:
    tree = ast.parse(PIPELINE_SOURCE.read_text(encoding="utf-8"))
    export_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "export_web_snapshot":
            export_calls.append(node)
    assert len(export_calls) == 1
    call = export_calls[0]
    assert isinstance(call.args[2], ast.Name)
    assert call.args[2].id == "breadth_timeseries"
    assert isinstance(call.args[3], ast.Name)
    assert call.args[3].id == "trend_timeseries"


def test_successful_export_writes_five_file_snapshot(tmp_path: Path) -> None:
    web_dir = tmp_path / "web-data"
    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=False,
            run_id="five-file-snapshot",
            generated_at=FIXED_GENERATED_AT,
            interpret_complete=_complete_from_messages,
            export_web_snapshot=True,
            web_snapshot_directory=web_dir,
        ),
    )
    assert result.exit_code == ExitCode.SUCCESS
    documents = {
        name: json.loads((web_dir / name).read_text(encoding="utf-8"))
        for name in SNAPSHOT_FILES
    }
    run_ids = {
        documents[MANIFEST_FILENAME]["run_id"],
        documents[QUANT_FILENAME]["run_metadata"]["run_id"],
        documents[MARKET_FILENAME]["run_id"],
        documents[BREADTH_FILENAME]["run_id"],
        documents[TREND_FILENAME]["run_id"],
    }
    as_of_dates = {
        documents[MANIFEST_FILENAME]["as_of_date"],
        documents[QUANT_FILENAME]["run_metadata"]["as_of_date"],
        documents[MARKET_FILENAME]["as_of_date"],
        documents[BREADTH_FILENAME]["as_of_date"],
        documents[TREND_FILENAME]["as_of_date"],
    }
    assert run_ids == {"five-file-snapshot"}
    assert len(as_of_dates) == 1
    assert documents[BREADTH_FILENAME]["series"]
    assert documents[TREND_FILENAME]["series"]
    assert (result.run_directory / "quant_summary.json").is_file()


def test_export_failure_does_not_delete_core_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args, **_kwargs):
        raise WebExportError("invalid snapshot")

    monkeypatch.setattr("src.pipeline.export_web_snapshot", boom)
    web_dir = tmp_path / "web-data"
    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=True,
            run_id="export-failure",
            generated_at=FIXED_GENERATED_AT,
            export_web_snapshot=True,
            web_snapshot_directory=web_dir,
        ),
    )
    run_dir = result.run_directory
    assert result.exit_code == ExitCode.PARTIAL
    assert any("web snapshot export failed" in warning for warning in result.warnings)
    assert (run_dir / "quant_summary.json").is_file()
    assert (run_dir / "market_summary.json").is_file()
    assert (run_dir / "market_report.md").is_file()
    assert (run_dir / "breadth_timeseries.png").is_file()
    assert not (web_dir / QUANT_FILENAME).exists()
    assert "web_snapshot" not in result.artifacts


def test_cli_export_run_bundle_flag_is_accepted() -> None:
    parsed = build_parser().parse_args(
        ["--export-run-bundle", "--run-bundle-dir", "/tmp/run-bundle"]
    )
    assert parsed.export_run_bundle is True
    assert parsed.run_bundle_dir == Path("/tmp/run-bundle")


def test_run_bundle_export_writes_outside_public_data(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "live-bundle"
    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=True,
            run_id="live-bundle-run",
            generated_at=FIXED_GENERATED_AT,
            export_run_bundle=True,
            run_bundle_directory=bundle_dir,
        ),
    )
    assert result.exit_code == ExitCode.PARTIAL
    assert (bundle_dir / QUANT_FILENAME).is_file()
    assert (bundle_dir / BREADTH_FILENAME).is_file()
    assert (bundle_dir / TREND_FILENAME).is_file()
    public = tmp_path / "web" / "public" / "data"
    assert not public.exists()
    assert "run_bundle" in result.artifacts
