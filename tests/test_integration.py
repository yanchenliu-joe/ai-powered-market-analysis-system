"""Offline end-to-end tests for the accepted Phase 2–9 workflow."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.config import load_config
from src.interpretation import SKIPPED_REASON
from src.pipeline import RunOptions, execute_analysis
from src.reporting import FALLBACK_DISCLAIMER, UNAVAILABLE_INTERPRETATION_NOTE
from src.schemas import MarketInterpretation, QuantSummary

FIXED_GENERATED_AT = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)
REQUIRED_REPORT_HEADINGS = [
    "## Executive Summary",
    "## Market Participation",
    "## Trend Conditions",
    "## Sector Rate Sensitivity",
    "## Data Quality",
    "## Methodology and Limitations",
    "## Disclaimer",
]
ARTIFACTS = (
    "quant_summary.json",
    "breadth_timeseries.png",
    "spy_trend.png",
    "sector_rate_beta.png",
    "market_summary.json",
    "market_report.md",
    "market_report.pdf",
)


def _config(tmp_path: Path):
    config = load_config(load_env_file=False)
    config.data.raw_directory = tmp_path / "raw"
    config.output.directory = tmp_path / "outputs"
    config.data.raw_directory.mkdir(parents=True)
    config.output.directory.mkdir(parents=True)
    return config


def _complete_from_messages(
    messages: list[dict[str, str]], model: str, timeout: float
) -> dict:
    del model, timeout
    content = messages[1]["content"]
    pack = json.loads(content[content.index("{") :])
    trend_regime = pack["spy_trend"]["trend_regime"]
    pct_50 = pack["breadth"]["pct_above_50dma"]
    sma_200 = pack["spy_trend"]["sma_200"]
    first = pack["sector_rate_sensitivity"][0]
    label = first["sensitivity_label"]
    sector = first["sector"]
    refs = [
        {
            "metric": "trend_regime",
            "value": trend_regime,
            "source_section": "spy_trend",
        },
        {
            "metric": "pct_above_50dma",
            "value": pct_50,
            "source_section": "breadth",
        },
        {
            "metric": "sma_200",
            "value": sma_200,
            "source_section": "spy_trend",
        },
        {
            "metric": f"{sector}.sensitivity_label",
            "value": label,
            "source_section": "sector_rate_sensitivity",
        },
    ]
    return {
        "market_regime_summary": {
            "summary": f"Accepted trend regime is {trend_regime}.",
            "evidence": refs[:1],
            "confidence": "high",
        },
        "breadth_interpretation": {
            "summary": f"Participation pct_above_50dma is {pct_50}.",
            "evidence": [refs[1]],
            "confidence": "medium",
        },
        "trend_interpretation": {
            "summary": f"SMA200 remains {sma_200} in the validated snapshot.",
            "evidence": [refs[2]],
            "confidence": "high",
        },
        "rates_and_sectors_interpretation": {
            "summary": f"{sector} sensitivity_label is {label}.",
            "evidence": [refs[3]],
            "confidence": "medium",
        },
        "key_confirmed_signals": [f"trend_regime={trend_regime}"],
        "key_uncertainties": ["Regression describes association, not causation."],
        "risk_flags": [],
        "evidence_used": refs,
        "evidence": refs,
        "executive_summary": f"Accepted trend regime is {trend_regime}.",
        "market_participation": f"Participation pct_above_50dma is {pct_50}.",
        "trend_conditions": f"SMA200 remains {sma_200} in the validated snapshot.",
        "sector_rate_risk": f"{sector} sensitivity_label is {label}.",
        "risks_and_limitations": "Regression describes association, not causation.",
        "disclaimer": (
            "This report is for research and educational purposes only and does not "
            "constitute investment advice."
        ),
    }


def test_fixture_pipeline_produces_complete_mocked_ai_artifacts(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    result = execute_analysis(
        config,
        RunOptions(
            fixture=True,
            skip_openai=False,
            run_id="fixture-acceptance",
            generated_at=FIXED_GENERATED_AT,
            interpret_complete=_complete_from_messages,
        ),
    )
    run_dir = result.run_directory
    summary = QuantSummary.model_validate_json(
        (run_dir / "quant_summary.json").read_text(encoding="utf-8")
    )
    market = MarketInterpretation.model_validate_json(
        (run_dir / "market_summary.json").read_text(encoding="utf-8")
    )
    report = (run_dir / "market_report.md").read_text(encoding="utf-8")
    quant_text = (run_dir / "quant_summary.json").read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert result.run_id == "fixture-acceptance"
    for name in ARTIFACTS:
        assert (run_dir / name).is_file()
    assert summary.run_metadata.run_id == market.run_id == "fixture-acceptance"
    assert summary.run_metadata.as_of_date == market.as_of_date
    assert [row.ticker for row in summary.sector_regressions] == list(
        config.data.sector_tickers
    )
    assert market.status.value == "available"
    assert market.executive_summary
    assert market.market_participation
    assert market.trend_conditions
    assert market.sector_rate_risk
    assert market.risks_and_limitations
    assert market.evidence
    assert market.disclaimer
    for heading in REQUIRED_REPORT_HEADINGS:
        assert heading in report
    assert "breadth_timeseries.png" in report
    assert "spy_trend.png" in report
    assert "sector_rate_beta.png" in report
    assert "NaN" not in quant_text
    assert "Infinity" not in quant_text
    json.dumps(json.loads(quant_text), allow_nan=False)


def test_fixture_quantitative_content_is_deterministic(tmp_path: Path) -> None:
    first_config = _config(tmp_path / "a")
    second_config = _config(tmp_path / "b")
    first = execute_analysis(
        first_config,
        RunOptions(
            fixture=True,
            skip_openai=True,
            run_id="det-a",
            generated_at=FIXED_GENERATED_AT,
        ),
    )
    second = execute_analysis(
        second_config,
        RunOptions(
            fixture=True,
            skip_openai=True,
            run_id="det-b",
            generated_at=FIXED_GENERATED_AT,
        ),
    )
    first_payload = json.loads(
        (first.run_directory / "quant_summary.json").read_text(encoding="utf-8")
    )
    second_payload = json.loads(
        (second.run_directory / "quant_summary.json").read_text(encoding="utf-8")
    )
    first_payload["run_metadata"]["run_id"] = "same"
    second_payload["run_metadata"]["run_id"] = "same"
    assert first_payload == second_payload


def test_openai_failure_after_quant_is_partial(tmp_path: Path) -> None:
    calls = {"count": 0}

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        calls["count"] += 1
        raise TimeoutError("openai timeout")

    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=False,
            run_id="openai-fail",
            generated_at=FIXED_GENERATED_AT,
            interpret_complete=complete,
        ),
    )
    run_dir = result.run_directory
    market = MarketInterpretation.model_validate_json(
        (run_dir / "market_summary.json").read_text(encoding="utf-8")
    )
    report = (run_dir / "market_report.md").read_text(encoding="utf-8")

    assert result.exit_code == 2
    assert (run_dir / "quant_summary.json").is_file()
    assert (run_dir / "breadth_timeseries.png").is_file()
    assert market.status.value == "unavailable"
    assert UNAVAILABLE_INTERPRETATION_NOTE in report
    assert FALLBACK_DISCLAIMER in report
    assert "markets are likely" not in report.lower()
    assert calls["count"] >= 1


def test_skip_openai_is_partial_and_offline(tmp_path: Path) -> None:
    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=True,
            run_id="skip-ai",
            generated_at=FIXED_GENERATED_AT,
        ),
    )
    market = MarketInterpretation.model_validate_json(
        (result.run_directory / "market_summary.json").read_text(encoding="utf-8")
    )
    assert result.exit_code == 2
    assert market.reason == SKIPPED_REASON
    assert market.status.value == "unavailable"
    assert (result.run_directory / "market_report.md").is_file()


def test_critical_quant_failure_does_not_call_openai(tmp_path: Path) -> None:
    called = {"openai": False}

    def exploding_universe() -> None:
        raise RuntimeError("should not load")

    def complete(messages: list[dict[str, str]], model: str, timeout: float) -> dict:
        called["openai"] = True
        return {}

    def bad_prices(tickers: list[str], start, end):
        raise RuntimeError("provider down")

    result = execute_analysis(
        _config(tmp_path),
        RunOptions(
            fixture=True,
            skip_openai=False,
            run_id="quant-fail",
            generated_at=FIXED_GENERATED_AT,
            interpret_complete=complete,
            price_provider=bad_prices,
        ),
    )
    run_dir = result.run_directory
    assert result.exit_code == 1
    assert called["openai"] is False
    assert not (run_dir / "quant_summary.json").exists()
    assert not (run_dir / "market_report.md").exists()
    del exploding_universe
