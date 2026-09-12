"""Deterministic tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.config import ENVIRONMENT_OVERRIDES, load_config


@pytest.fixture(autouse=True)
def clean_configuration_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (*ENVIRONMENT_OVERRIDES, "OPENAI_MODEL", "OPENAI_API_KEY"):
        monkeypatch.delenv(variable, raising=False)


def test_default_configuration_loads_with_expected_values() -> None:
    config = load_config(load_env_file=False)

    assert config.analysis.regression_window == 252
    assert config.analysis.min_regression_obs == 200
    assert config.analysis.moving_average_windows == [20, 50, 200]
    assert config.data.benchmark_ticker == "SPY"
    assert config.data.treasury_series == "DGS10"
    assert len(config.data.sector_tickers) == 11
    assert config.data.raw_directory.is_absolute()
    assert config.data.yield_unit == "percentage_points"
    assert config.output.directory.is_absolute()


def test_environment_overrides_are_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_ANALYSIS_REGRESSION_WINDOW", "300")
    monkeypatch.setenv("MARKET_ANALYSIS_BENCHMARK_TICKER", "IVV")
    monkeypatch.setenv("MARKET_ANALYSIS_RAW_DATA_DIRECTORY", "custom/raw")
    monkeypatch.setenv("MARKET_ANALYSIS_LOG_LEVEL", "debug")
    monkeypatch.setenv("OPENAI_MODEL", "environment-model")

    config = load_config(load_env_file=False)

    assert config.analysis.regression_window == 300
    assert config.data.benchmark_ticker == "IVV"
    assert config.data.raw_directory.name == "raw"
    assert config.logging.level == "DEBUG"
    assert config.llm.model == "environment-model"


def test_cli_overrides_have_highest_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_ANALYSIS_LOG_LEVEL", "WARNING")

    config = load_config(cli_overrides={"logging.level": "DEBUG"}, load_env_file=False)

    assert config.logging.level == "DEBUG"


def test_invalid_configuration_raises_clear_error(tmp_path: Path) -> None:
    invalid_config = {
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
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text(yaml.safe_dump(invalid_config), encoding="utf-8")

    with pytest.raises(ValidationError, match="regression_window"):
        load_config(config_path, load_env_file=False)
