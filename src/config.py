"""Typed configuration loading for the market analysis application."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"


class StrictModel(BaseModel):
    """Base model that rejects unknown configuration keys."""

    model_config = ConfigDict(extra="forbid")


class AnalysisConfig(StrictModel):
    regression_window: PositiveInt
    min_regression_obs: PositiveInt
    moving_average_windows: list[PositiveInt]

    @field_validator("moving_average_windows")
    @classmethod
    def validate_moving_average_windows(
        cls, windows: list[PositiveInt]
    ) -> list[PositiveInt]:
        if not windows:
            raise ValueError("moving_average_windows must not be empty")
        if len(set(windows)) != len(windows):
            raise ValueError("moving_average_windows must contain unique values")
        return windows


class DataConfig(StrictModel):
    benchmark_ticker: str = Field(min_length=1)
    raw_directory: Path
    sector_tickers: list[str]
    treasury_series: str = Field(min_length=1)
    yield_unit: Literal["percentage_points"]

    @field_validator("sector_tickers")
    @classmethod
    def validate_sector_tickers(cls, tickers: list[str]) -> list[str]:
        if not tickers:
            raise ValueError("sector_tickers must not be empty")
        if any(not ticker.strip() for ticker in tickers):
            raise ValueError("sector_tickers must not contain empty values")
        return tickers


class OutputConfig(StrictModel):
    directory: Path


class LoggingConfig(StrictModel):
    level: str

    @field_validator("level")
    @classmethod
    def normalize_level(cls, level: str) -> str:
        normalized = level.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError(f"unsupported logging level: {level}")
        return normalized


class LLMConfig(StrictModel):
    model_env_var: str = Field(min_length=1)
    model: str | None = None


class AppConfig(StrictModel):
    """Validated application configuration."""

    analysis: AnalysisConfig
    data: DataConfig
    output: OutputConfig
    logging: LoggingConfig
    llm: LLMConfig


ENVIRONMENT_OVERRIDES: dict[str, tuple[str, str]] = {
    "MARKET_ANALYSIS_REGRESSION_WINDOW": ("analysis", "regression_window"),
    "MARKET_ANALYSIS_MIN_REGRESSION_OBS": ("analysis", "min_regression_obs"),
    "MARKET_ANALYSIS_BENCHMARK_TICKER": ("data", "benchmark_ticker"),
    "MARKET_ANALYSIS_RAW_DATA_DIRECTORY": ("data", "raw_directory"),
    "MARKET_ANALYSIS_TREASURY_SERIES": ("data", "treasury_series"),
    "MARKET_ANALYSIS_OUTPUT_DIRECTORY": ("output", "directory"),
    "MARKET_ANALYSIS_LOG_LEVEL": ("logging", "level"),
}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"configuration file not found: {path}")
    with path.open(encoding="utf-8") as config_file:
        contents = yaml.safe_load(config_file)
    if not isinstance(contents, dict):
        raise ValueError(f"configuration must be a YAML mapping: {path}")
    return contents


def _apply_environment(config_data: dict[str, Any]) -> None:
    for variable, (section, key) in ENVIRONMENT_OVERRIDES.items():
        value = os.getenv(variable)
        if value is not None:
            config_data[section][key] = value

    model_env_var = config_data.get("llm", {}).get("model_env_var")
    if model_env_var:
        config_data["llm"]["model"] = os.getenv(model_env_var)


def _apply_cli_overrides(
    config_data: dict[str, Any], cli_overrides: dict[str, Any]
) -> None:
    for dotted_key, value in cli_overrides.items():
        if value is None:
            continue
        section, separator, key = dotted_key.partition(".")
        if (
            not separator
            or section not in config_data
            or key not in config_data[section]
        ):
            raise ValueError(f"unsupported CLI configuration override: {dotted_key}")
        config_data[section][key] = value


def _resolve_paths(config: AppConfig, config_path: Path) -> AppConfig:
    # Default and project-local config files use stable project-relative paths.
    base_directory = (
        PROJECT_ROOT
        if config_path == DEFAULT_CONFIG_PATH or PROJECT_ROOT in config_path.parents
        else config_path.parent
    )
    for owner, attribute in (
        (config.data, "raw_directory"),
        (config.output, "directory"),
    ):
        directory = getattr(owner, attribute)
        resolved = (
            (base_directory / directory).resolve()
            if not directory.is_absolute()
            else directory.resolve()
        )
        setattr(owner, attribute, resolved)
    return config


def load_config(
    config_path: str | Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
    *,
    load_env_file: bool = True,
) -> AppConfig:
    """Load config with precedence: CLI overrides, environment, then YAML."""

    if load_env_file:
        load_dotenv(PROJECT_ROOT / ".env", override=False)

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()

    config_data = copy.deepcopy(_read_yaml(path))
    _apply_environment(config_data)
    _apply_cli_overrides(config_data, cli_overrides or {})
    config = AppConfig.model_validate(config_data)
    return _resolve_paths(config, path)
