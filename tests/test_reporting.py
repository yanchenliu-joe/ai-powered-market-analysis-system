"""Deterministic tests for Phase 9 Markdown report assembly."""

from __future__ import annotations

import ast
import copy
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from src.display import (
    display_trend_regime,
    format_advance_decline_ratio,
    format_beta,
    format_breadth_momentum,
    format_breadth_percent,
    format_distance_percent,
    format_effect_10bp,
    format_p_value,
    format_price,
)
from src.quant_pipeline import write_quant_summary
from src.reporting import (
    EXPECTED_CHARTS,
    EXPECTED_SECTORS,
    FALLBACK_DISCLAIMER,
    REPORT_FILENAME,
    REPORT_TEMP_FILENAME,
    UNAVAILABLE,
    UNAVAILABLE_INTERPRETATION_NOTE,
    VISUALIZATION_UNAVAILABLE_NOTE,
    ReportError,
    assemble_report_markdown,
    generate_report,
    generate_report_file,
    ordered_sector_records,
    render_number,
    write_report_markdown,
)
from src.schemas import EvidenceReference, MarketInterpretation, QuantSummary
from tests.test_schemas import (
    insufficient_regression,
    valid_regression,
    valid_summary_payload,
)

GENERATED_AT = datetime(2024, 1, 2, 15, 30, tzinfo=UTC)
REPORTING_SOURCE = Path(__file__).resolve().parents[1] / "src" / "reporting.py"
REQUIRED_HEADINGS = [
    "# AI-Powered Market Analysis System",
    "## Executive Summary",
    "## Market Participation",
    "## Trend Conditions",
    "## Sector Rate Sensitivity",
    "## Data Quality",
    "## Methodology and Limitations",
    "## Disclaimer",
]


def _summary() -> QuantSummary:
    payload = copy.deepcopy(valid_summary_payload())
    payload["data_quality"]["warnings"] = ["Provider gap on one DGS10 date."]
    return QuantSummary.model_validate(payload)


def _eleven_sector_summary(*, insufficient_last: bool = False) -> QuantSummary:
    payload = copy.deepcopy(valid_summary_payload())
    records = []
    insufficient_count = 0
    for ticker in EXPECTED_SECTORS:
        if insufficient_last and ticker == "XLU":
            records.append(insufficient_regression(ticker))
            insufficient_count += 1
        else:
            records.append(valid_regression(ticker))
    payload["sector_regressions"] = records
    payload["data_quality"]["sector_result_count"] = 11
    payload["data_quality"]["valid_sector_count"] = 11 - insufficient_count
    payload["data_quality"]["insufficient_sector_count"] = insufficient_count
    payload["data_quality"]["available_sector_tickers"] = 11
    payload["data_quality"]["warnings"] = ["Provider gap on one DGS10 date."]
    if insufficient_count:
        payload["status"] = "partial"
    return QuantSummary.model_validate(payload)


def _section(
    summary_text: str,
    *,
    metric: str = "trend_regime",
    value: object = "strong_uptrend",
    source_section: str = "spy_trend",
    confidence: str = "high",
) -> dict[str, object]:
    return {
        "summary": summary_text,
        "evidence": [
            {
                "metric": metric,
                "value": value,
                "source_section": source_section,
            }
        ],
        "confidence": confidence,
    }


def _available_interpretation(summary: QuantSummary) -> MarketInterpretation:
    regime = summary.trend.trend_regime.value
    return MarketInterpretation.model_validate(
        {
            "run_id": summary.run_metadata.run_id,
            "as_of_date": summary.run_metadata.as_of_date,
            "status": "available",
            "model": "test-model",
            "generated_at": GENERATED_AT,
            "market_regime_summary": _section(f"Accepted trend regime is {regime}."),
            "breadth_interpretation": _section(
                "Participation is copied from the validated snapshot.",
                metric="pct_above_50dma",
                value=summary.breadth.pct_above_50dma,
                source_section="breadth",
                confidence="medium",
            ),
            "trend_interpretation": _section(
                "SMA values are not recomputed.",
                metric="sma_200",
                value=summary.trend.sma_200,
                source_section="spy_trend",
            ),
            "rates_and_sectors_interpretation": _section(
                "Sector labels are preserved exactly.",
                metric="XLK.sensitivity_label",
                value="negative_significant",
                source_section="sector_rate_sensitivity",
                confidence="medium",
            ),
            "key_confirmed_signals": [f"trend_regime={regime}"],
            "key_uncertainties": ["Regression describes association, not causation."],
            "risk_flags": [],
            "evidence_used": [
                {
                    "metric": "trend_regime",
                    "value": regime,
                    "source_section": "spy_trend",
                }
            ],
            "executive_summary": "EXEC_SUMMARY_PROSE",
            "market_participation": "MARKET_PARTICIPATION_PROSE",
            "trend_conditions": "TREND_CONDITIONS_PROSE",
            "sector_rate_risk": "SECTOR_RATE_RISK_PROSE",
            "risks_and_limitations": "RISKS_AND_LIMITATIONS_PROSE",
            "disclaimer": "VALIDATED_DISCLAIMER_PROSE",
        }
    )


def _unavailable_interpretation(
    summary: QuantSummary,
    reason: str = "missing_api_key",
) -> MarketInterpretation:
    return MarketInterpretation.model_validate(
        {
            "run_id": summary.run_metadata.run_id,
            "as_of_date": summary.run_metadata.as_of_date,
            "status": "unavailable",
            "reason": reason,
            "generated_at": GENERATED_AT,
        }
    )


def _touch_charts(run_directory: Path) -> None:
    run_directory.mkdir(parents=True, exist_ok=True)
    for name in EXPECTED_CHARTS:
        (run_directory / name).write_bytes(b"png")


def _section_body(markdown: str, heading: str, next_heading: str) -> str:
    start = markdown.index(heading)
    end = markdown.index(next_heading)
    return markdown[start:end]


def test_successful_report_has_stable_structure_and_charts(tmp_path: Path) -> None:
    summary = _eleven_sector_summary()
    interpretation = _available_interpretation(summary)
    _touch_charts(tmp_path / "fixed-run")
    artifact = generate_report(summary, interpretation, output_directory=tmp_path)
    markdown = artifact.path.read_text(encoding="utf-8")
    positions = [markdown.index(heading) for heading in REQUIRED_HEADINGS]
    participation = _section_body(
        markdown, "## Market Participation", "## Trend Conditions"
    )
    trend_body = _section_body(
        markdown, "## Trend Conditions", "## Sector Rate Sensitivity"
    )
    sector_body = _section_body(
        markdown, "## Sector Rate Sensitivity", "## Data Quality"
    )
    method_body = _section_body(
        markdown, "## Methodology and Limitations", "## Disclaimer"
    )
    exec_body = _section_body(
        markdown, "## Executive Summary", "## Market Participation"
    )
    disclaimer_body = markdown[markdown.index("## Disclaimer") :]

    assert artifact.path == tmp_path / "fixed-run" / REPORT_FILENAME
    assert not (tmp_path / "fixed-run" / "report.md").exists()
    assert artifact.run_id == "fixed-run"
    assert artifact.as_of_date == date(2023, 12, 29)
    assert positions == sorted(positions)
    assert "As of: 2023-12-29" in markdown
    assert "Run ID: fixed-run" in markdown
    assert "## Interpretation" not in markdown
    assert "EXEC_SUMMARY_PROSE" in exec_body
    assert "MARKET_PARTICIPATION_PROSE" in participation
    assert "TREND_CONDITIONS_PROSE" in trend_body
    assert "SECTOR_RATE_RISK_PROSE" in sector_body
    assert "RISKS_AND_LIMITATIONS_PROSE" in method_body
    assert "VALIDATED_DISCLAIMER_PROSE" in disclaimer_body
    assert "![Market breadth time series](breadth_timeseries.png)" in markdown
    assert "![SPY trend](spy_trend.png)" in markdown
    assert "![Sector rate sensitivity](sector_rate_beta.png)" in markdown
    assert markdown.index("| XLC |") < markdown.index("| XLK |")
    assert markdown.index("| XLK |") < markdown.index("| XLU |")
    assert markdown.endswith("\n")
    assert "buy" not in markdown.lower()
    assert artifact.missing_visualizations == ()


def test_data_quality_uses_validated_quant_summary_fields() -> None:
    summary = _summary()
    markdown = assemble_report_markdown(
        summary,
        _available_interpretation(summary),
        present_charts=set(EXPECTED_CHARTS),
    )
    quality = _section_body(
        markdown, "## Data Quality", "## Methodology and Limitations"
    )

    assert "Available equity tickers / universe size: 3 / 3" in quality
    assert "Latest 50DMA valid count: 3" in quality
    assert "Latest 200DMA valid count: 3" in quality
    assert "SPY observation coverage (cleaned / raw): 220 / 220" in quality
    assert "DGS10 usable observation coverage (usable / raw): 270 / 270" in quality
    assert "Available sectors: 11" in quality or "Available sectors: 1" in quality
    assert "Valid regressions: 1" in quality
    assert "Insufficient regressions: 0" in quality
    assert "Provider gap on one DGS10 date." in quality


def test_sector_table_preserves_project_order() -> None:
    summary = _eleven_sector_summary()
    tickers = [record.ticker for record in ordered_sector_records(summary)]

    assert tickers == list(EXPECTED_SECTORS)


def test_interpretation_unavailable_keeps_required_sections(
    tmp_path: Path,
) -> None:
    summary = _summary()
    interpretation = _unavailable_interpretation(summary)
    _touch_charts(tmp_path / "fixed-run")
    artifact = generate_report(summary, interpretation, output_directory=tmp_path)
    markdown = artifact.path.read_text(encoding="utf-8")

    assert artifact.path.name == REPORT_FILENAME
    assert not (artifact.path.parent / "report.md").exists()
    for heading in REQUIRED_HEADINGS:
        assert heading in markdown
    assert UNAVAILABLE_INTERPRETATION_NOTE in markdown
    assert FALLBACK_DISCLAIMER in markdown
    assert "## Interpretation" not in markdown
    assert "EXEC_SUMMARY_PROSE" not in markdown
    assert "MARKET_PARTICIPATION_PROSE" not in markdown
    assert "TREND_CONDITIONS_PROSE" not in markdown
    assert "SECTOR_RATE_RISK_PROSE" not in markdown
    assert "RISKS_AND_LIMITATIONS_PROSE" not in markdown
    assert "Accepted trend regime is" not in markdown
    assert "markets are likely" not in markdown.lower()
    assert artifact.interpretation_status.value == "unavailable"


def test_missing_numeric_values_render_as_unavailable() -> None:
    payload = copy.deepcopy(valid_summary_payload())
    payload["breadth"]["pct_above_50dma"] = 0.0
    payload["breadth"]["pct_above_200dma"] = None
    payload["breadth"]["valid_count_200dma"] = 0
    payload["breadth"]["above_200dma_count"] = 0
    payload["breadth"]["unavailable_fields"] = ["pct_above_200dma"]
    payload["trend"]["sma_20"] = None
    payload["trend"]["distance_to_sma_20"] = None
    payload["trend"]["sma_50"] = None
    payload["trend"]["distance_to_sma_50"] = None
    payload["breadth"]["pct_above_50dma"] = 0.0
    summary = QuantSummary.model_validate(payload)
    markdown = assemble_report_markdown(
        summary, _unavailable_interpretation(summary), present_charts=set()
    )

    assert "% Above 50DMA: 0.0%" in markdown
    assert "% Above 200DMA: Unavailable" in markdown
    assert "SMA20: Unavailable" in markdown
    assert "SMA50: Unavailable" in markdown
    assert "% Above 200DMA: 0" not in markdown
    assert "Unavailable fields: pct_above_200dma" in markdown
    assert "corresponding moving-average window was incomplete" in markdown


def test_insufficient_sectors_remain_visible_without_fabricated_beta() -> None:
    summary = _eleven_sector_summary(insufficient_last=True)
    markdown = assemble_report_markdown(
        summary,
        _available_interpretation(summary),
        present_charts=set(EXPECTED_CHARTS),
    )
    rows = [line for line in markdown.splitlines() if line.startswith("| XLU |")]

    assert len(rows) == 1
    assert f"| XLU | {UNAVAILABLE} | {UNAVAILABLE} | {UNAVAILABLE} | " in rows[0]
    assert "Insufficient Data" in rows[0]
    assert "insufficient_data" not in rows[0]
    assert "| XLU | 0 |" not in markdown
    assert "Insufficient-data sector records: XLU." in markdown


def test_missing_png_does_not_block_report(tmp_path: Path) -> None:
    summary = _summary()
    artifact = generate_report(
        summary,
        _available_interpretation(summary),
        output_directory=tmp_path,
    )
    markdown = artifact.path.read_text(encoding="utf-8")

    assert artifact.path.exists()
    assert artifact.path.name == REPORT_FILENAME
    assert markdown.count(VISUALIZATION_UNAVAILABLE_NOTE) == 3
    assert "![Market breadth time series]" not in markdown
    assert artifact.missing_visualizations == EXPECTED_CHARTS


def test_run_id_mismatch_does_not_write_report(tmp_path: Path) -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary).model_copy(
        update={"run_id": "other-run"}
    )

    with pytest.raises(ReportError, match="run_id mismatch"):
        generate_report(summary, interpretation, output_directory=tmp_path)
    assert not (tmp_path / "fixed-run" / REPORT_FILENAME).exists()
    assert not (tmp_path / "fixed-run" / "report.md").exists()
    assert not (tmp_path / "other-run" / REPORT_FILENAME).exists()


def test_as_of_date_mismatch_does_not_write_report(tmp_path: Path) -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary).model_copy(
        update={"as_of_date": date(2023, 1, 2)}
    )

    with pytest.raises(ReportError, match="as_of_date mismatch"):
        generate_report(summary, interpretation, output_directory=tmp_path)
    assert not (tmp_path / "fixed-run" / REPORT_FILENAME).exists()


def test_generate_report_file_rejects_directory_run_id_mismatch(
    tmp_path: Path,
) -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary)
    write_quant_summary(summary, tmp_path)
    wrong = tmp_path / "other-run"
    wrong.mkdir()
    (wrong / "quant_summary.json").write_text(
        (tmp_path / "fixed-run" / "quant_summary.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (wrong / "market_summary.json").write_text(
        interpretation.model_dump_json(), encoding="utf-8"
    )

    with pytest.raises(ReportError, match="does not match run_id"):
        generate_report_file(wrong)
    assert not (wrong / REPORT_FILENAME).exists()
    assert not (wrong / "report.md").exists()


def test_generate_report_file_round_trip(tmp_path: Path) -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary)
    run_directory = write_quant_summary(summary, tmp_path).parent
    (run_directory / "market_summary.json").write_text(
        interpretation.model_dump_json(), encoding="utf-8"
    )
    _touch_charts(run_directory)

    artifact = generate_report_file(run_directory)

    assert artifact.path == run_directory / REPORT_FILENAME
    assert not (run_directory / "report.md").exists()
    assert "Run ID: fixed-run" in artifact.path.read_text(encoding="utf-8")


def test_missing_input_artifacts_raise(tmp_path: Path) -> None:
    run_directory = tmp_path / "fixed-run"
    run_directory.mkdir()

    with pytest.raises(ReportError, match="missing quant summary"):
        generate_report_file(run_directory)
    (run_directory / "quant_summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ReportError, match="missing market summary"):
        generate_report_file(run_directory)


def test_generate_report_accepts_run_directory_as_output(tmp_path: Path) -> None:
    summary = _summary()
    run_directory = tmp_path / "fixed-run"
    _touch_charts(run_directory)
    artifact = generate_report(
        summary,
        _available_interpretation(summary),
        output_directory=run_directory,
    )

    assert artifact.path == run_directory / REPORT_FILENAME


def test_unexpected_sector_appended_after_project_order() -> None:
    payload = copy.deepcopy(valid_summary_payload())
    payload["sector_regressions"] = [
        valid_regression("ZZZ"),
        valid_regression("XLK"),
    ]
    payload["data_quality"]["sector_result_count"] = 2
    payload["data_quality"]["valid_sector_count"] = 2
    summary = QuantSummary.model_validate(payload)
    tickers = [record.ticker for record in ordered_sector_records(summary)]

    assert tickers == ["XLK", "ZZZ"]


def test_write_report_markdown_terminates_with_newline(tmp_path: Path) -> None:
    path = write_report_markdown("# Report", tmp_path / "fixed-run")

    assert path.read_text(encoding="utf-8") == "# Report\n"
    run_directory = tmp_path / "fixed-run"
    path = write_report_markdown("# Report\n", run_directory)

    assert path.read_text(encoding="utf-8") == "# Report\n"
    assert path.name == REPORT_FILENAME
    assert not (run_directory / REPORT_TEMP_FILENAME).exists()
    assert not (run_directory / ".report.md.tmp").exists()


def test_write_failure_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(ReportError, match="unable to write"):
        write_report_markdown("# Report\n", tmp_path / "fixed-run")
    assert not (tmp_path / "fixed-run" / REPORT_TEMP_FILENAME).exists()
    assert not (tmp_path / "fixed-run" / ".report.md.tmp").exists()


def test_markdown_is_deterministic() -> None:
    summary = _eleven_sector_summary(insufficient_last=True)
    interpretation = _available_interpretation(summary)
    first = assemble_report_markdown(
        summary, interpretation, present_charts=set(EXPECTED_CHARTS)
    )
    second = assemble_report_markdown(
        summary, interpretation, present_charts=set(EXPECTED_CHARTS)
    )

    assert first == second
    assert "generated_at" not in first


def test_render_number_rejects_booleans() -> None:
    with pytest.raises(ReportError, match="boolean"):
        render_number(True)  # type: ignore[arg-type]
    assert render_number(0) == "0"
    assert render_number(0.0) == "0"
    assert render_number(None) == UNAVAILABLE


def test_spec_fields_fall_back_to_existing_sections() -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary).model_copy(
        update={
            "risk_flags": ["liquidity gap"],
            "evidence": [
                EvidenceReference.model_validate(
                    {
                        "metric": "pct_above_50dma",
                        "value": 66.67,
                        "source_section": "breadth",
                    }
                )
            ],
            "evidence_used": [
                EvidenceReference.model_validate(
                    {
                        "metric": "pct_above_50dma",
                        "value": 66.67,
                        "source_section": "breadth",
                    }
                )
            ],
        }
    )
    markdown = assemble_report_markdown(
        summary, interpretation, present_charts=set(EXPECTED_CHARTS)
    )

    assert "EXEC_SUMMARY_PROSE" in markdown
    assert "MARKET_PARTICIPATION_PROSE" in markdown
    assert "liquidity gap" in markdown
    assert "`pct_above_50dma` (breadth): 66.67" in markdown


def test_evidence_none_and_string_values_render() -> None:
    summary = _summary()
    interpretation = _available_interpretation(summary)
    mutated = interpretation.model_copy(
        update={
            "evidence_used": [
                interpretation.evidence_used[0].model_copy(update={"value": None}),
                interpretation.evidence_used[0],
            ],
            "evidence": [
                interpretation.evidence_used[0].model_copy(update={"value": None}),
                interpretation.evidence_used[0],
            ],
        }
    )
    markdown = assemble_report_markdown(
        summary, mutated, present_charts=set(EXPECTED_CHARTS)
    )

    assert "`trend_regime` (spy_trend): Unavailable" in markdown
    assert "`trend_regime` (spy_trend): strong_uptrend" in markdown


def test_report_formats_human_readable_numbers_without_changing_source() -> None:
    payload = copy.deepcopy(valid_summary_payload())
    payload["breadth"]["pct_above_50dma"] = 38.1237525
    payload["breadth"]["pct_above_200dma"] = 58.51703407
    payload["breadth"]["advance_decline_ratio"] = 2.29605263
    payload["breadth"]["breadth_momentum_20d"] = -30.4762475
    payload["trend"]["adjusted_close"] = 765.63000488
    payload["trend"]["sma_20"] = 766.94599609
    payload["trend"]["sma_50"] = 758.6432019
    payload["trend"]["sma_200"] = 712.06452637
    payload["trend"]["distance_to_sma_20"] = -0.00171589
    payload["trend"]["distance_to_sma_50"] = 0.0092096
    payload["trend"]["distance_to_sma_200"] = 0.0752256
    payload["trend"]["trend_regime"] = "uptrend"
    payload["sector_regressions"] = [
        {
            **valid_regression("XLK"),
            "beta_yield": -0.0646915,
            "ci_95_lower": -0.09661022,
            "ci_95_upper": -0.03277278,
            "p_value": 0.00008627,
            "effect_10bp": -0.00646915,
        },
        {
            **valid_regression("XLU"),
            "p_value": 0.10373995,
            "beta_yield": -0.02608147,
            "ci_95_lower": -0.05753845,
            "ci_95_upper": 0.0053755,
            "effect_10bp": -0.00260815,
            "sensitivity_label": "negative_not_significant",
        },
    ]
    payload["data_quality"]["sector_result_count"] = 2
    payload["data_quality"]["valid_sector_count"] = 2
    summary = QuantSummary.model_validate(payload)
    markdown = assemble_report_markdown(
        summary, _unavailable_interpretation(summary), present_charts=set()
    )
    stored = summary.model_dump()

    assert "% Above 50DMA: 38.1%" in markdown
    assert "% Above 200DMA: 58.5%" in markdown
    assert "Advance/Decline Ratio: 2.30" in markdown
    assert "Breadth Momentum (20D): -30.5 percentage points" in markdown
    assert "Adjusted Close: $765.63" in markdown
    assert "SMA20: $766.95" in markdown
    assert "SMA50: $758.64" in markdown
    assert "SMA200: $712.06" in markdown
    assert "Distance to SMA20: -0.17%" in markdown
    assert "Distance to SMA50: +0.92%" in markdown
    assert "Trend regime: Uptrend" in markdown
    assert "strong_uptrend" not in markdown
    assert "| XLK | -0.0647 | [-0.0966, -0.0328] | <0.001 | 252 | -0.65% |" in markdown
    assert "| XLU |" in markdown and "0.104" in markdown
    assert "Negative — Significant" in markdown
    assert "Negative — Not Significant" in markdown
    assert stored["breadth"]["pct_above_50dma"] == 38.1237525
    assert stored["trend"]["trend_regime"] == "uptrend"
    assert stored["trend"]["distance_to_sma_50"] == 0.0092096
    assert summary.trend.trend_regime.value == "uptrend"
    assert display_trend_regime("uptrend") == "Uptrend"
    assert format_breadth_percent(38.1237525) == "38.1%"
    assert format_breadth_momentum(-30.4762475) == "-30.5 percentage points"
    assert format_advance_decline_ratio(2.29605263) == "2.30"
    assert format_price(765.63000488) == "$765.63"
    assert format_distance_percent(0.0092096) == "+0.92%"
    assert format_beta(-0.0646915) == "-0.0647"
    assert format_p_value(0.00008627) == "<0.001"
    assert format_p_value(0.10373995) == "0.104"
    assert format_effect_10bp(-0.00646915) == "-0.65%"


def test_duplicate_survivorship_limitations_are_removed_once() -> None:
    payload = copy.deepcopy(valid_summary_payload())
    payload["limitations"] = [
        (
            "Historical breadth uses current S&P 500 membership and is "
            "subject to survivorship bias."
        ),
        (
            "Historical analysis uses the current S&P 500 constituent universe "
            "and is subject to survivorship bias; point-in-time membership is "
            "not used."
        ),
        "Sector regressions estimate association, not causation.",
        "One-factor daily regressions omit other market and macro factors.",
        "A cache gap reduced DGS10 coverage on one holiday.",
    ]
    summary = QuantSummary.model_validate(payload)
    markdown = assemble_report_markdown(
        summary, _unavailable_interpretation(summary), present_charts=set()
    )
    method_body = _section_body(
        markdown, "## Methodology and Limitations", "## Disclaimer"
    )
    lowered = method_body.lower()

    assert lowered.count("survivorship") == 1
    assert "association is not" in lowered
    assert "omits other market and macro factors" in lowered
    assert "percentage points" in lowered
    assert "cache gap reduced dgs10 coverage" in lowered
    assert method_body.count("4.30 to 4.35") == 1


def test_reporting_module_does_not_import_engines_or_openai() -> None:
    tree = ast.parse(REPORTING_SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)

    forbidden = {
        "openai",
        "yfinance",
        "pandas_datareader",
        "src.data_loader",
        "src.preprocessing",
        "src.breadth",
        "src.trend",
        "src.regression",
        "src.visualization",
        "src.interpretation",
        "src.quant_pipeline",
        "data_loader",
        "breadth",
        "trend",
        "regression",
        "visualization",
        "interpretation",
    }
    assert imported.isdisjoint(forbidden)
    assert "src.schemas" in imported
