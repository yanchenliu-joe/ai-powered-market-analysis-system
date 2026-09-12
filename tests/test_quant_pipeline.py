"""Offline integration tests for the Phase 6 quantitative pipeline."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.quant_pipeline as pipeline_module
from src.config import load_config
from src.data_loader import AcquisitionMetadata
from src.quant_pipeline import (
    ASSOCIATION_LIMITATION,
    SURVIVORSHIP_LIMITATION,
    AcquisitionContext,
    QuantPipelineError,
    run_quant_pipeline,
    serialize_quant_summary,
    write_quant_summary,
)
from src.schemas import QuantSummary

FIXED_RUN_ID = "phase-6-fixed-run"
FIXED_GENERATED_AT = datetime(2024, 2, 1, 12, 30, tzinfo=UTC)
SECTORS = ["XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLK", "XLB", "XLRE", "XLU"]


def quantitative_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    equity_dates = pd.bdate_range("2023-01-02", periods=230)
    equity_records: list[dict[str, object]] = []
    patterns = {
        "AAA": 100.0 + np.arange(230) * 0.5,
        "BBB": 300.0 - np.arange(230) * 0.4,
        "CCC": 80.0 + np.arange(230) * 0.2,
    }
    for ticker, prices in patterns.items():
        equity_records.extend(
            {
                "date": day,
                "ticker": ticker,
                "adjusted_close": price,
            }
            for day, price in zip(equity_dates, prices, strict=True)
        )
    equities = pd.DataFrame(equity_records)
    spy = pd.DataFrame(
        {
            "date": equity_dates[:225],
            "adjusted_close": 400.0 + np.arange(225) * 0.5,
        }
    )

    regression_dates = pd.bdate_range("2023-01-02", periods=271)
    steps = np.arange(270, dtype=float)
    yield_changes = 0.04 * np.sin(steps / 7.0) + 0.01 * np.cos(steps / 11.0)
    treasury = pd.DataFrame(
        {
            "date": regression_dates,
            "yield_percent": np.concatenate(([4.0], 4.0 + np.cumsum(yield_changes))),
        }
    )
    sector_records: list[dict[str, object]] = []
    for sector_index, ticker in enumerate(SECTORS):
        direction = -1.0 if sector_index % 2 else 1.0
        beta = direction * (0.01 + sector_index * 0.001)
        noise = 0.0002 * np.cos(steps / (5.0 + sector_index))
        returns = 0.0005 + beta * yield_changes + noise
        prices = 100.0 * np.cumprod(np.concatenate(([1.0], 1.0 + returns)))
        sector_records.extend(
            {
                "date": day,
                "ticker": ticker,
                "adjusted_close": price,
            }
            for day, price in zip(regression_dates, prices, strict=True)
        )
    sectors = pd.DataFrame(sector_records)
    return equities, spy, sectors, treasury


def acquisition_metadata(
    dataset: str,
    provider: str,
    rows: int,
    identifier: str | list[str],
    *,
    exclusions: list[str] | None = None,
    errors: list[str] | None = None,
    limitations: list[str] | None = None,
) -> AcquisitionMetadata:
    return AcquisitionMetadata(
        dataset=dataset,
        provider=provider,
        requested_start="2023-01-02",
        requested_end="2024-02-01",
        download_timestamp="2024-02-01T12:00:00+00:00",
        cache_used=False,
        raw_row_count=rows,
        cleaned_row_count=rows,
        identifier=identifier,
        price_treatment=(
            "Adj Close from auto_adjust=False" if dataset != "dgs10" else None
        ),
        unit="percentage_points" if dataset == "dgs10" else None,
        exclusions=exclusions or [],
        errors=errors or [],
        limitations=limitations or [],
    )


def context_for(
    equities: pd.DataFrame,
    spy: pd.DataFrame,
    sectors: pd.DataFrame,
    treasury: pd.DataFrame,
) -> AcquisitionContext:
    return AcquisitionContext(
        universe=acquisition_metadata(
            "sp500_universe",
            "wikipedia",
            3,
            ["AAA", "BBB", "CCC"],
            limitations=["Historical analysis uses the current constituent universe."],
        ),
        equities=acquisition_metadata(
            "equities",
            "yfinance",
            len(equities),
            ["AAA", "BBB", "CCC"],
            exclusions=["one test exclusion"],
        ),
        spy=acquisition_metadata("spy", "yfinance", len(spy), "SPY"),
        sectors=acquisition_metadata("sectors", "yfinance", len(sectors), SECTORS),
        treasury=acquisition_metadata("dgs10", "fred", len(treasury), "DGS10"),
    )


def run_fixture_pipeline(
    *,
    sectors_to_truncate: tuple[str, ...] = (),
) -> QuantSummary:
    equities, spy, sectors, treasury = quantitative_inputs()
    for ticker in sectors_to_truncate:
        ticker_dates = sectors.loc[sectors["ticker"] == ticker, "date"].sort_values()
        cutoff = ticker_dates.iloc[150]
        sectors = sectors[(sectors["ticker"] != ticker) | (sectors["date"] <= cutoff)]
    config = load_config(load_env_file=False)
    return run_quant_pipeline(
        equities,
        spy,
        sectors,
        treasury,
        config=config,
        acquisition_context=context_for(equities, spy, sectors, treasury),
        analysis_start=date(2023, 1, 2),
        analysis_end=date(2024, 2, 1),
        run_id=FIXED_RUN_ID,
        generated_at=FIXED_GENERATED_AT,
    )


def test_full_pipeline_reuses_modules_and_produces_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    equities, spy, sectors, treasury = quantitative_inputs()
    calls = {"breadth": 0, "trend": 0, "regression": 0}
    original_breadth = pipeline_module.compute_breadth_timeseries
    original_trend = pipeline_module.compute_trend_timeseries
    original_regression = pipeline_module.run_sector_regressions

    def breadth_wrapper(data: pd.DataFrame):
        calls["breadth"] += 1
        return original_breadth(data)

    def trend_wrapper(data: pd.DataFrame):
        calls["trend"] += 1
        return original_trend(data)

    def regression_wrapper(*args: object, **kwargs: object):
        calls["regression"] += 1
        return original_regression(*args, **kwargs)

    monkeypatch.setattr(pipeline_module, "compute_breadth_timeseries", breadth_wrapper)
    monkeypatch.setattr(pipeline_module, "compute_trend_timeseries", trend_wrapper)
    monkeypatch.setattr(pipeline_module, "run_sector_regressions", regression_wrapper)
    config = load_config(load_env_file=False)

    summary = run_quant_pipeline(
        equities,
        spy,
        sectors,
        treasury,
        config=config,
        acquisition_context=context_for(equities, spy, sectors, treasury),
        analysis_start=date(2023, 1, 2),
        analysis_end=date(2024, 2, 1),
        run_id=FIXED_RUN_ID,
        generated_at=FIXED_GENERATED_AT,
    )

    assert isinstance(summary, QuantSummary)
    assert summary.status == "success"
    assert calls == {"breadth": 1, "trend": 1, "regression": 1}
    assert [result.ticker for result in summary.sector_regressions] == SECTORS
    assert summary.run_metadata.run_id == FIXED_RUN_ID
    assert summary.run_metadata.data_sources.price_provider == "yfinance"
    assert summary.run_metadata.data_sources.treasury_provider == "fred"


def test_as_of_date_uses_actual_common_supported_market_date() -> None:
    equities, spy, sectors, treasury = quantitative_inputs()
    nominal_end = spy["date"].max().date() + timedelta(days=30)
    config = load_config(load_env_file=False)

    summary = run_quant_pipeline(
        equities,
        spy,
        sectors,
        treasury,
        config=config,
        acquisition_context=context_for(equities, spy, sectors, treasury),
        analysis_start=date(2023, 1, 2),
        analysis_end=nominal_end,
        run_id=FIXED_RUN_ID,
        generated_at=FIXED_GENERATED_AT,
    )

    assert summary.run_metadata.as_of_date == spy["date"].max().date()
    assert summary.run_metadata.as_of_date < nominal_end
    assert summary.breadth.as_of_date == summary.trend.as_of_date


def test_data_quality_counts_and_supplied_warnings_are_preserved() -> None:
    summary = run_fixture_pipeline()
    quality = summary.data_quality

    assert quality.available_equity_tickers == 3
    assert quality.universe_size == 3
    assert quality.latest_50dma_valid_count == 3
    assert quality.latest_200dma_valid_count == 3
    assert quality.spy_observation_count == 225
    assert quality.dgs10_usable_observation_count == 271
    assert quality.available_sector_tickers == 11
    assert quality.sector_result_count == 11
    assert quality.valid_sector_count == 11
    assert quality.insufficient_sector_count == 0
    assert quality.exclusions == ["one test exclusion"]


def test_default_limitations_are_present() -> None:
    summary = run_fixture_pipeline()

    assert SURVIVORSHIP_LIMITATION in summary.limitations
    assert ASSOCIATION_LIMITATION in summary.limitations
    assert any("omit other market" in item for item in summary.limitations)


@pytest.mark.parametrize("insufficient_tickers", [("XLRE",), ("XLRE", "XLB", "XLC")])
def test_noncritical_insufficient_sectors_produce_partial(
    insufficient_tickers: tuple[str, ...],
) -> None:
    summary = run_fixture_pipeline(sectors_to_truncate=insufficient_tickers)

    assert summary.status == "partial"
    assert summary.data_quality.insufficient_sector_count == len(insufficient_tickers)
    by_ticker = {result.ticker: result for result in summary.sector_regressions}
    for ticker in insufficient_tickers:
        assert by_ticker[ticker].status == "insufficient_data"
        assert by_ticker[ticker].beta_yield is None


@pytest.mark.parametrize("critical_input", ["equities", "spy"])
def test_malformed_core_market_input_is_a_critical_failure(
    critical_input: str,
) -> None:
    equities, spy, sectors, treasury = quantitative_inputs()
    if critical_input == "equities":
        equities = equities.drop(columns="adjusted_close")
    else:
        spy = spy.drop(columns="adjusted_close")
    config = load_config(load_env_file=False)

    with pytest.raises(QuantPipelineError, match="critical") as error:
        run_quant_pipeline(
            equities,
            spy,
            sectors,
            treasury,
            config=config,
            acquisition_context=context_for(equities, spy, sectors, treasury),
            analysis_start=date(2023, 1, 2),
            analysis_end=date(2024, 2, 1),
            run_id=FIXED_RUN_ID,
            generated_at=FIXED_GENERATED_AT,
        )
    assert error.value.status == "failure"


def test_malformed_treasury_causing_no_regressions_is_failure() -> None:
    equities, spy, sectors, treasury = quantitative_inputs()
    malformed_treasury = treasury.drop(columns="yield_percent")
    config = load_config(load_env_file=False)

    with pytest.raises(QuantPipelineError, match="no usable sector"):
        run_quant_pipeline(
            equities,
            spy,
            sectors,
            malformed_treasury,
            config=config,
            acquisition_context=context_for(equities, spy, sectors, treasury),
            analysis_start=date(2023, 1, 2),
            analysis_end=date(2024, 2, 1),
            run_id=FIXED_RUN_ID,
            generated_at=FIXED_GENERATED_AT,
        )


def test_repeated_injected_identity_and_timestamp_are_deterministic() -> None:
    first = run_fixture_pipeline()
    second = run_fixture_pipeline()

    assert serialize_quant_summary(first) == serialize_quant_summary(second)


def test_output_is_written_to_run_directory_and_validates_on_read(
    tmp_path: Path,
) -> None:
    summary = run_fixture_pipeline()

    output_path = write_quant_summary(summary, tmp_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    revalidated = QuantSummary.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )

    assert output_path == tmp_path / FIXED_RUN_ID / "quant_summary.json"
    assert parsed["run_metadata"]["run_id"] == FIXED_RUN_ID
    assert revalidated == summary
    assert not (output_path.parent / ".quant_summary.json.tmp").exists()


def test_failed_atomic_replace_preserves_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary = run_fixture_pipeline()
    output_path = write_quant_summary(summary, tmp_path)
    original_content = output_path.read_text(encoding="utf-8")

    def fail_replace(_self: Path, _target: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(QuantPipelineError, match="unable to write"):
        write_quant_summary(summary, tmp_path)

    assert output_path.read_text(encoding="utf-8") == original_content
    assert not (output_path.parent / ".quant_summary.json.tmp").exists()
