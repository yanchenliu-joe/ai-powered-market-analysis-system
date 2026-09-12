"""CLI tests for the integrated market analysis application."""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.config import ENVIRONMENT_OVERRIDES, load_config
from src.main import ExitCode, build_parser, main
from src.pipeline import RunOptions, execute_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FUTURE_MODULES = [
    "data_loader",
    "preprocessing",
    "breadth",
    "trend",
    "regression",
    "schemas",
    "quant_pipeline",
    "llm_analyzer",
    "interpretation",
    "visualization",
    "reporting",
    "report_generator",
    "pipeline",
    "fixture_data",
]


def test_cli_help_succeeds() -> None:
    assert main(["-h"]) == ExitCode.SUCCESS
    help_text = build_parser().format_help()
    assert "--skip-openai" in help_text
    assert "--fixture" in help_text
    assert "--run-id" in help_text
    assert "--force-refresh" in help_text
    assert "--export-web-snapshot" in help_text
    assert "--web-snapshot-dir" in help_text
    assert "--export-run-bundle" in help_text
    assert "--run-bundle-dir" in help_text


def test_fixture_skip_openai_cli_returns_partial(tmp_path: Path) -> None:
    code = main(
        [
            "--fixture",
            "--skip-openai",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "cli-fixture",
            "--log-level",
            "INFO",
        ]
    )
    run_dir = tmp_path / "outputs" / "cli-fixture"
    assert code == ExitCode.PARTIAL
    assert (run_dir / "quant_summary.json").is_file()
    assert (run_dir / "market_summary.json").is_file()
    assert (run_dir / "market_report.md").is_file()
    assert (run_dir / "market_report.pdf").is_file()


def test_module_cli_fixture_does_not_require_openai_key(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "--fixture",
            "--skip-openai",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "cli-subprocess",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == ExitCode.PARTIAL
    assert "sk-" not in result.stdout
    assert "sk-" not in result.stderr


def test_skip_openai_does_not_call_live_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import interpretation

    def fail_live(*args: object, **kwargs: object) -> dict:
        raise AssertionError("live OpenAI client must not be called")

    monkeypatch.setattr(interpretation, "_live_complete", fail_live)
    code = main(
        [
            "--fixture",
            "--skip-openai",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "no-live",
        ]
    )
    assert code == ExitCode.PARTIAL


def test_force_refresh_reaches_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import pipeline as pipeline_module

    config = load_config(load_env_file=False)
    config.data.raw_directory = tmp_path / "raw"
    config.output.directory = tmp_path / "outputs"
    config.data.raw_directory.mkdir()
    config.output.directory.mkdir()
    seen: list[bool] = []
    original = pipeline_module.load_equity_prices

    def wrapped(*args: object, **kwargs: object):
        seen.append(bool(kwargs.get("force_refresh")))
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline_module, "load_equity_prices", wrapped)
    execute_analysis(
        config,
        RunOptions(
            fixture=True,
            skip_openai=True,
            force_refresh=True,
            run_id="fr",
        ),
    )
    assert seen and seen[0] is True


def test_supplied_run_id_is_preserved(tmp_path: Path) -> None:
    code = main(
        [
            "--fixture",
            "--skip-openai",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "custom-run-id",
        ]
    )
    assert code == ExitCode.PARTIAL
    assert (tmp_path / "outputs" / "custom-run-id" / "quant_summary.json").is_file()


def test_invalid_config_exits_failure(tmp_path: Path) -> None:
    assert main(["--config", str(tmp_path / "missing.yaml")]) == ExitCode.FAILURE


def test_invalid_yaml_config_exits_failure(tmp_path: Path) -> None:
    invalid = {
        "analysis": {
            "regression_window": 0,
            "min_regression_obs": 200,
            "moving_average_windows": [20, 50, 200],
        },
        "data": {
            "benchmark_ticker": "SPY",
            "raw_directory": "data/raw",
            "sector_tickers": ["XLK"],
            "treasury_series": "DGS10",
            "yield_unit": "percentage_points",
        },
        "output": {"directory": "outputs"},
        "logging": {"level": "INFO"},
        "llm": {"model_env_var": "OPENAI_MODEL"},
    }
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(invalid), encoding="utf-8")
    assert main(["--config", str(path)]) == ExitCode.FAILURE


def test_quant_failure_exits_failure(tmp_path: Path) -> None:
    config = load_config(load_env_file=False)
    config.data.raw_directory = tmp_path / "raw"
    config.output.directory = tmp_path / "outputs"
    config.data.raw_directory.mkdir()
    config.output.directory.mkdir()

    def bad_provider(tickers: list[str], start: object, end: object) -> None:
        raise RuntimeError("no prices")

    result = execute_analysis(
        config,
        RunOptions(
            fixture=True,
            skip_openai=False,
            price_provider=bad_provider,
            run_id="fail-quant",
        ),
    )
    assert result.exit_code == ExitCode.FAILURE
    assert not (result.run_directory / "quant_summary.json").exists()


def test_secrets_are_not_logged(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    caplog.set_level(logging.INFO)
    code = main(
        [
            "--fixture",
            "--skip-openai",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "secret-check",
            "--log-level",
            "INFO",
        ]
    )
    assert code == ExitCode.PARTIAL
    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert "sk-test-secret-value" not in combined


@pytest.mark.parametrize("module_name", FUTURE_MODULES)
def test_future_placeholder_module_imports(module_name: str) -> None:
    imported = importlib.import_module(f"src.{module_name}")
    assert imported.__doc__


def test_environment_overrides_still_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ENVIRONMENT_OVERRIDES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("MARKET_ANALYSIS_LOG_LEVEL", "ERROR")
    config = load_config(load_env_file=False)
    assert config.logging.level == "ERROR"
