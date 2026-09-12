"""Validation and strict-serialization tests for Phase 6 schemas."""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime

import numpy as np
import pytest
from pydantic import ValidationError

from src.quant_pipeline import serialize_quant_summary
from src.schemas import (
    SCHEMA_VERSION,
    BreadthSummary,
    DataQuality,
    DataSources,
    QuantSummary,
    RunMetadata,
    SectorRegressionSummary,
    TrendSummary,
)


def valid_regression(ticker: str = "XLK") -> dict[str, object]:
    return {
        "ticker": ticker,
        "alpha": 0.001,
        "beta_yield": -0.02,
        "beta_std_error": 0.005,
        "beta_t_value": -4.0,
        "p_value": 0.001,
        "ci_95_lower": -0.03,
        "ci_95_upper": -0.01,
        "r_squared": 0.25,
        "adjusted_r_squared": 0.24,
        "n_obs": 252,
        "start_date": date(2023, 1, 2),
        "end_date": date(2023, 12, 29),
        "effect_10bp": -0.002,
        "sensitivity_label": "negative_significant",
        "status": "success",
        "error_reason": None,
    }


def insufficient_regression(ticker: str = "XLRE") -> dict[str, object]:
    return {
        "ticker": ticker,
        "alpha": None,
        "beta_yield": None,
        "beta_std_error": None,
        "beta_t_value": None,
        "p_value": None,
        "ci_95_lower": None,
        "ci_95_upper": None,
        "r_squared": None,
        "adjusted_r_squared": None,
        "n_obs": 150,
        "start_date": date(2023, 1, 2),
        "end_date": date(2023, 8, 1),
        "effect_10bp": None,
        "sensitivity_label": "insufficient_data",
        "status": "insufficient_data",
        "error_reason": "requires at least 200 observations",
    }


def valid_summary_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "run_metadata": {
            "run_id": "fixed-run",
            "as_of_date": date(2023, 12, 29),
            "generated_at": datetime(2024, 1, 2, 12, 0, tzinfo=UTC),
            "schema_version": "1.0.0",
            "analysis_start": date(2023, 1, 2),
            "analysis_end": date(2024, 1, 1),
            "regression_window": 252,
            "min_regression_obs": 200,
            "moving_average_windows": [20, 50, 200],
            "yield_unit": "percentage_points",
            "data_sources": {
                "price_provider": "yfinance",
                "treasury_provider": "fred",
                "universe_provider": "wikipedia",
            },
        },
        "data_quality": {
            "requested_start": date(2023, 1, 2),
            "requested_end": date(2024, 1, 1),
            "equity_raw_row_count": 600,
            "equity_cleaned_row_count": 600,
            "available_equity_tickers": 3,
            "universe_size": 3,
            "latest_50dma_valid_count": 3,
            "latest_200dma_valid_count": 3,
            "spy_raw_row_count": 220,
            "spy_cleaned_row_count": 220,
            "spy_observation_count": 220,
            "dgs10_raw_row_count": 270,
            "dgs10_cleaned_row_count": 270,
            "dgs10_usable_observation_count": 270,
            "sector_raw_row_count": 3000,
            "sector_cleaned_row_count": 3000,
            "available_sector_tickers": 11,
            "sector_result_count": 1,
            "valid_sector_count": 1,
            "insufficient_sector_count": 0,
            "exclusions": [],
            "warnings": [],
        },
        "breadth": {
            "as_of_date": date(2023, 12, 29),
            "pct_above_50dma": 66.67,
            "above_50dma_count": 2,
            "valid_count_50dma": 3,
            "pct_above_200dma": 66.67,
            "above_200dma_count": 2,
            "valid_count_200dma": 3,
            "advancers": 2,
            "decliners": 1,
            "valid_return_count": 3,
            "advance_decline_ratio": 2.0,
            "net_advances": 1,
            "breadth_momentum_20d": 0.0,
            "status": "available",
            "unavailable_fields": [],
        },
        "trend": {
            "as_of_date": date(2023, 12, 29),
            "adjusted_close": 475.0,
            "sma_20": 470.0,
            "sma_50": 460.0,
            "sma_200": 430.0,
            "distance_to_sma_20": 475 / 470 - 1,
            "distance_to_sma_50": 475 / 460 - 1,
            "distance_to_sma_200": 475 / 430 - 1,
            "trend_regime": "strong_uptrend",
        },
        "sector_regressions": [valid_regression()],
        "limitations": [
            "Historical breadth may use current constituents.",
            "Regression is association, not causation.",
        ],
        "status": "success",
    }


def test_valid_quant_summary_and_schema_version() -> None:
    summary = QuantSummary.model_validate(valid_summary_payload())

    assert summary.schema_version == SCHEMA_VERSION == "1.0.0"
    assert summary.run_metadata.yield_unit == "percentage_points"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("status",), "unknown"),
        (("trend", "trend_regime"), "bullish"),
        (
            ("sector_regressions", 0, "sensitivity_label"),
            "rate_sensitive",
        ),
        (("run_metadata", "yield_unit"), "decimal"),
    ],
)
def test_controlled_enums_reject_unknown_values(
    path: tuple[str | int, ...], value: object
) -> None:
    payload = copy.deepcopy(valid_summary_payload())
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ValidationError):
        QuantSummary.model_validate(payload)


@pytest.mark.parametrize("percentage", [100.01, -0.01])
def test_breadth_percentage_bounds_are_enforced(percentage: float) -> None:
    payload = valid_summary_payload()["breadth"]
    payload["pct_above_50dma"] = percentage  # type: ignore[index]

    with pytest.raises(ValidationError):
        BreadthSummary.model_validate(payload)


def test_breadth_numerator_cannot_exceed_denominator() -> None:
    payload = valid_summary_payload()["breadth"]
    payload["above_200dma_count"] = 4  # type: ignore[index]

    with pytest.raises(ValidationError, match="exceeds"):
        BreadthSummary.model_validate(payload)


@pytest.mark.parametrize("p_value", [-0.01, 1.01])
def test_regression_p_value_bounds_are_enforced(p_value: float) -> None:
    payload = valid_regression()
    payload["p_value"] = p_value

    with pytest.raises(ValidationError):
        SectorRegressionSummary.model_validate(payload)


def test_regression_ci_order_and_beta_containment_are_enforced() -> None:
    reversed_ci = valid_regression()
    reversed_ci["ci_95_lower"] = 0.0
    reversed_ci["ci_95_upper"] = -0.04
    outside_ci = valid_regression()
    outside_ci["beta_yield"] = -0.05

    with pytest.raises(ValidationError, match="reversed"):
        SectorRegressionSummary.model_validate(reversed_ci)
    with pytest.raises(ValidationError, match="outside"):
        SectorRegressionSummary.model_validate(outside_ci)


def test_negative_observations_and_reversed_dates_are_rejected() -> None:
    negative = valid_regression()
    negative["n_obs"] = -1
    reversed_dates = valid_regression()
    reversed_dates["start_date"] = date(2024, 1, 1)

    with pytest.raises(ValidationError):
        SectorRegressionSummary.model_validate(negative)
    with pytest.raises(ValidationError, match="start_date"):
        SectorRegressionSummary.model_validate(reversed_dates)


def test_insufficient_regression_allows_null_statistics() -> None:
    result = SectorRegressionSummary.model_validate(insufficient_regression())

    assert result.status == "insufficient_data"
    assert result.beta_yield is None
    assert result.p_value is None


@pytest.mark.parametrize("nonfinite", [np.nan, np.inf, -np.inf])
def test_nonfinite_schema_values_are_rejected(nonfinite: float) -> None:
    payload = valid_regression()
    payload["beta_yield"] = nonfinite

    with pytest.raises(ValidationError):
        SectorRegressionSummary.model_validate(payload)


def test_limitations_must_be_nonempty_and_factual_strings() -> None:
    payload = valid_summary_payload()
    payload["limitations"] = []
    with pytest.raises(ValidationError):
        QuantSummary.model_validate(payload)

    payload["limitations"] = [""]
    with pytest.raises(ValidationError):
        QuantSummary.model_validate(payload)


def test_strict_serialization_is_standard_json_and_iso_formatted() -> None:
    summary = QuantSummary.model_validate(valid_summary_payload())
    serialized = serialize_quant_summary(summary)
    parsed = json.loads(serialized)

    assert "NaN" not in serialized
    assert "Infinity" not in serialized
    assert "-Infinity" not in serialized
    assert parsed["run_metadata"]["as_of_date"] == "2023-12-29"
    assert parsed["run_metadata"]["generated_at"] == "2024-01-02T12:00:00Z"
    assert parsed["sector_regressions"][0]["start_date"] == "2023-01-02"
    json.dumps(parsed, allow_nan=False)


def test_unavailable_values_serialize_as_null() -> None:
    payload = valid_summary_payload()
    payload["sector_regressions"] = [insufficient_regression()]  # type: ignore[index]
    payload["data_quality"]["valid_sector_count"] = 0  # type: ignore[index]
    payload["data_quality"]["insufficient_sector_count"] = 1  # type: ignore[index]
    payload["status"] = "partial"
    summary = QuantSummary.model_validate(payload)

    parsed = json.loads(serialize_quant_summary(summary))

    assert parsed["sector_regressions"][0]["beta_yield"] is None
    assert parsed["sector_regressions"][0]["p_value"] is None


def test_serialization_is_deterministic_for_identical_models() -> None:
    first = QuantSummary.model_validate(valid_summary_payload())
    second = QuantSummary.model_validate(valid_summary_payload())

    assert serialize_quant_summary(first) == serialize_quant_summary(second)


def test_nested_model_construction_is_explicit() -> None:
    payload = valid_summary_payload()

    assert isinstance(RunMetadata.model_validate(payload["run_metadata"]), RunMetadata)
    assert isinstance(DataQuality.model_validate(payload["data_quality"]), DataQuality)
    assert isinstance(BreadthSummary.model_validate(payload["breadth"]), BreadthSummary)
    assert isinstance(TrendSummary.model_validate(payload["trend"]), TrendSummary)
    assert isinstance(
        DataSources.model_validate(payload["run_metadata"]["data_sources"]),  # type: ignore[index]
        DataSources,
    )
