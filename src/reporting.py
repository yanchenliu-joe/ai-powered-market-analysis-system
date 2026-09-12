"""Deterministic Markdown assembly from validated run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.display import (
    UNAVAILABLE,
    display_sensitivity_label,
    display_trend_regime,
    format_advance_decline_ratio,
    format_beta,
    format_breadth_momentum,
    format_breadth_percent,
    format_ci,
    format_distance_percent,
    format_effect_10bp,
    format_p_value,
    format_price,
    unique_limitation_texts,
)
from src.schemas import (
    InterpretationSection,
    InterpretationStatus,
    MarketInterpretation,
    QuantSummary,
    SectorRegressionSummary,
)

EXPECTED_SECTORS = (
    "XLC",
    "XLY",
    "XLP",
    "XLE",
    "XLF",
    "XLV",
    "XLI",
    "XLK",
    "XLB",
    "XLRE",
    "XLU",
)

EXPECTED_CHARTS = (
    "breadth_timeseries.png",
    "spy_trend.png",
    "sector_rate_beta.png",
)

REPORT_FILENAME = "market_report.md"
REPORT_TEMP_FILENAME = ".market_report.md.tmp"

UNAVAILABLE_INTERPRETATION_NOTE = (
    "AI interpretation was unavailable for this run. "
    "Quantitative results below remain valid."
)
VISUALIZATION_UNAVAILABLE_NOTE = "Visualization unavailable for this run."
FALLBACK_DISCLAIMER = (
    "This report is for research and educational purposes only and does not "
    "constitute investment advice."
)

METHODOLOGY = """\
Breadth indicators measure how many constituents with a complete moving-average
window sit strictly above their 50-day and 200-day averages, together with
advance/decline counts from valid one-day returns. Missing history is excluded
from denominators rather than treated as below average.

SPY trend classification uses complete-window SMA20, SMA50, and SMA200 values
and the accepted regime labels from the quantitative layer. This report repeats
the stored `trend_regime` and does not reclassify it.

Sector yield regressions are one-factor daily associations between sector
returns and changes in the 10-year Treasury yield. A one-factor specification
omits other market and macro factors. Coefficients, confidence intervals, and
sensitivity labels are copied from the validated summary. Association is not
causation.

Historical breadth using the current S&P 500 constituent universe is subject
to survivorship bias.

The pipeline is deterministic through quantitative output and charts. OpenAI
interpretation is an optional later layer. This report only assembles already
validated artifacts and does not call a language model or recompute indicators.
"""


class ReportError(RuntimeError):
    """Raised when report inputs are inconsistent or cannot be written."""


@dataclass(frozen=True)
class ReportArtifact:
    run_id: str
    as_of_date: date
    path: Path
    interpretation_status: InterpretationStatus
    missing_visualizations: tuple[str, ...]


def render_number(value: int | float | None) -> str:
    """Render a validated numeric field without substituting zero for missing."""

    if value is None:
        return UNAVAILABLE
    if isinstance(value, bool):
        raise ReportError("boolean values are not reportable numeric fields")
    if isinstance(value, int):
        return str(value)
    return f"{value:.8f}".rstrip("0").rstrip(".")


def render_percent(value: float | None) -> str:
    return format_breadth_percent(value)


def render_ci(
    lower: float | None,
    upper: float | None,
) -> str:
    return format_ci(lower, upper)


def ordered_sector_records(
    summary: QuantSummary,
) -> list[SectorRegressionSummary]:
    by_ticker = {record.ticker: record for record in summary.sector_regressions}
    ordered: list[SectorRegressionSummary] = []
    for ticker in EXPECTED_SECTORS:
        record = by_ticker.pop(ticker, None)
        if record is not None:
            ordered.append(record)
    ordered.extend(by_ticker.values())
    return ordered


def _bullet_list(items: list[str], empty_text: str) -> list[str]:
    if not items:
        return [empty_text]
    return [f"- {item}" for item in items]


def _evidence_lines(references: list) -> list[str]:
    lines = ["", "Evidence:"]
    for reference in references:
        if reference.value is None:
            value = UNAVAILABLE
        elif isinstance(reference.value, (int, float)):
            value = render_number(reference.value)
        else:
            value = str(reference.value)
        lines.append(f"- `{reference.metric}` ({reference.source_section}): {value}")
    return lines


def _chart_block(filename: str, alt_text: str, present: bool) -> list[str]:
    if present:
        return ["", f"![{alt_text}]({filename})"]
    return ["", VISUALIZATION_UNAVAILABLE_NOTE]


def _section_summary(section: InterpretationSection | None) -> str | None:
    if section is None:
        return None
    return section.summary


def _resolved_prose(
    interpretation: MarketInterpretation,
    field_name: str,
    fallback_section: InterpretationSection | None = None,
) -> str | None:
    if interpretation.status is not InterpretationStatus.AVAILABLE:
        return None
    value = getattr(interpretation, field_name)
    if isinstance(value, str) and value.strip():
        return value
    return _section_summary(fallback_section)


def _validate_consistency(
    summary: QuantSummary, interpretation: MarketInterpretation
) -> None:
    quant_run = summary.run_metadata.run_id
    quant_date = summary.run_metadata.as_of_date
    if interpretation.run_id != quant_run:
        raise ReportError(
            f"run_id mismatch: quant={quant_run!r} interpretation="
            f"{interpretation.run_id!r}"
        )
    if interpretation.as_of_date != quant_date:
        raise ReportError(
            f"as_of_date mismatch: quant={quant_date.isoformat()} "
            f"interpretation={interpretation.as_of_date.isoformat()}"
        )


def resolve_run_directory(output_directory: str | Path, run_id: str) -> Path:
    path = Path(output_directory)
    if path.name == run_id:
        return path
    return path / run_id


def assemble_report_markdown(
    summary: QuantSummary,
    interpretation: MarketInterpretation,
    *,
    present_charts: set[str] | None = None,
) -> str:
    """Assemble deterministic Markdown from validated objects."""

    _validate_consistency(summary, interpretation)
    charts = present_charts if present_charts is not None else set(EXPECTED_CHARTS)
    as_of = summary.run_metadata.as_of_date.isoformat()
    run_id = summary.run_metadata.run_id
    breadth = summary.breadth
    trend = summary.trend
    quality = summary.data_quality
    available = interpretation.status is InterpretationStatus.AVAILABLE

    executive = _resolved_prose(
        interpretation, "executive_summary", interpretation.market_regime_summary
    )
    participation = _resolved_prose(
        interpretation,
        "market_participation",
        interpretation.breadth_interpretation,
    )
    trend_prose = _resolved_prose(
        interpretation, "trend_conditions", interpretation.trend_interpretation
    )
    sector_prose = _resolved_prose(
        interpretation,
        "sector_rate_risk",
        interpretation.rates_and_sectors_interpretation,
    )
    risks_prose = _resolved_prose(interpretation, "risks_and_limitations")
    if risks_prose is None and available and interpretation.key_uncertainties:
        risks_prose = " ".join(interpretation.key_uncertainties)

    lines = [
        "# AI-Powered Market Analysis System",
        "",
        f"As of: {as_of}",
        f"Run ID: {run_id}",
        "",
        "## Executive Summary",
        "",
    ]
    if available and executive is not None:
        lines.append(executive)
        if interpretation.key_confirmed_signals:
            lines.extend(["", "Confirmed signals:"])
            lines.extend(_bullet_list(interpretation.key_confirmed_signals, ""))
        if interpretation.risk_flags:
            lines.extend(["", "Risk flags:"])
            lines.extend(_bullet_list(interpretation.risk_flags, ""))
    else:
        lines.append(UNAVAILABLE_INTERPRETATION_NOTE)

    lines.extend(
        [
            "",
            "## Market Participation",
            "",
            f"- % Above 50DMA: {format_breadth_percent(breadth.pct_above_50dma)}",
            f"- % Above 200DMA: {format_breadth_percent(breadth.pct_above_200dma)}",
            f"- Advancers: {render_number(breadth.advancers)}",
            f"- Decliners: {render_number(breadth.decliners)}",
            "- Advance/Decline Ratio: "
            f"{format_advance_decline_ratio(breadth.advance_decline_ratio)}",
            "- Breadth Momentum (20D): "
            f"{format_breadth_momentum(breadth.breadth_momentum_20d)}",
            f"- Breadth status: {breadth.status.value}",
        ]
    )
    if breadth.unavailable_fields:
        joined = ", ".join(breadth.unavailable_fields)
        lines.append(f"- Unavailable fields: {joined}")
    if breadth.valid_count_50dma == 0 or breadth.valid_count_200dma == 0:
        lines.append(
            "- Some participation percentages are unavailable because the "
            "corresponding moving-average window was incomplete."
        )
    if participation is not None:
        lines.extend(["", participation])
    lines.extend(
        _chart_block(
            "breadth_timeseries.png",
            "Market breadth time series",
            "breadth_timeseries.png" in charts,
        )
    )

    lines.extend(
        [
            "",
            "## Trend Conditions",
            "",
            f"- Adjusted Close: {format_price(trend.adjusted_close)}",
            f"- SMA20: {format_price(trend.sma_20)}",
            f"- SMA50: {format_price(trend.sma_50)}",
            f"- SMA200: {format_price(trend.sma_200)}",
            f"- Distance to SMA20: {format_distance_percent(trend.distance_to_sma_20)}",
            f"- Distance to SMA50: {format_distance_percent(trend.distance_to_sma_50)}",
            "- Distance to SMA200: "
            f"{format_distance_percent(trend.distance_to_sma_200)}",
            f"- Trend regime: {display_trend_regime(trend.trend_regime.value)}",
        ]
    )
    if trend_prose is not None:
        lines.extend(["", trend_prose])
    lines.extend(_chart_block("spy_trend.png", "SPY trend", "spy_trend.png" in charts))

    lines.extend(
        [
            "",
            "## Sector Rate Sensitivity",
            "",
            "Yield unit: " f"{summary.run_metadata.yield_unit.replace('_', ' ')}.",
            "",
            "Sector yield coefficients describe statistical association and "
            "exposure, not causation.",
            "",
            "| Sector | Beta | 95% CI | p-value | Obs. | "
            "+10bp Effect | Significance |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in ordered_sector_records(summary):
        lines.append(
            "| "
            + " | ".join(
                [
                    record.ticker,
                    format_beta(record.beta_yield),
                    format_ci(record.ci_95_lower, record.ci_95_upper),
                    format_p_value(record.p_value),
                    render_number(record.n_obs),
                    format_effect_10bp(record.effect_10bp),
                    display_sensitivity_label(record.sensitivity_label.value),
                ]
            )
            + " |"
        )
    if sector_prose is not None:
        lines.extend(["", sector_prose])
    lines.extend(
        _chart_block(
            "sector_rate_beta.png",
            "Sector rate sensitivity",
            "sector_rate_beta.png" in charts,
        )
    )

    lines.extend(
        [
            "",
            "## Data Quality",
            "",
            "- Available equity tickers / universe size: "
            f"{quality.available_equity_tickers} / {quality.universe_size}",
            f"- Latest 50DMA valid count: {quality.latest_50dma_valid_count}",
            f"- Latest 200DMA valid count: {quality.latest_200dma_valid_count}",
            "- SPY observation coverage (cleaned / raw): "
            f"{quality.spy_cleaned_row_count} / {quality.spy_raw_row_count}",
            "- DGS10 usable observation coverage (usable / raw): "
            f"{quality.dgs10_usable_observation_count} / "
            f"{quality.dgs10_raw_row_count}",
            f"- Available sectors: {quality.available_sector_tickers}",
            f"- Valid regressions: {quality.valid_sector_count}",
            f"- Insufficient regressions: {quality.insufficient_sector_count}",
            "",
            "Exclusions:",
        ]
    )
    lines.extend(_bullet_list(list(quality.exclusions), "- None recorded."))
    lines.extend(["", "Warnings:"])
    lines.extend(_bullet_list(list(quality.warnings), "- None recorded."))

    yield_unit_note = (
        "Yield changes are measured in percentage points. A move from "
        "4.30 to 4.35 is 0.05, not 0.0005."
    )
    extra_limitations = unique_limitation_texts(
        [METHODOLOGY],
        list(summary.limitations),
        [risks_prose] if risks_prose else [],
        [yield_unit_note],
    )[1:]
    lines.extend(["", "## Methodology and Limitations", "", METHODOLOGY.rstrip(), ""])
    if extra_limitations:
        lines.append("Additional validated limitations:")
        lines.extend(_bullet_list(extra_limitations, "- None recorded."))
    insufficient = [
        record.ticker
        for record in ordered_sector_records(summary)
        if record.status.value == "insufficient_data"
    ]
    if insufficient:
        lines.extend(
            [
                "",
                "Insufficient-data sector records: " + ", ".join(insufficient) + ".",
            ]
        )
    missing = [name for name in EXPECTED_CHARTS if name not in charts]
    if missing:
        lines.extend(
            [
                "",
                "Missing visualization artifacts: " + ", ".join(missing) + ".",
            ]
        )
    if available and (interpretation.evidence or interpretation.evidence_used):
        lines.extend(
            _evidence_lines(
                list(interpretation.evidence or interpretation.evidence_used)
            )
        )

    disclaimer = FALLBACK_DISCLAIMER
    if available and interpretation.disclaimer and interpretation.disclaimer.strip():
        disclaimer = interpretation.disclaimer
    lines.extend(["", "## Disclaimer", "", disclaimer, ""])
    return "\n".join(lines)


def write_report_markdown(markdown: str, run_directory: str | Path) -> Path:
    """Atomically write outputs/<run_id>/market_report.md."""

    if not markdown.endswith("\n"):
        markdown += "\n"
    destination_dir = Path(run_directory)
    destination = destination_dir / REPORT_FILENAME
    temporary = destination_dir / REPORT_TEMP_FILENAME
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        temporary.write_text(markdown, encoding="utf-8")
        temporary.replace(destination)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ReportError(f"unable to write report: {destination}") from error
    return destination


def generate_report(
    summary: QuantSummary,
    interpretation: MarketInterpretation,
    *,
    output_directory: str | Path,
) -> ReportArtifact:
    """Assemble and persist market_report.md under outputs/<run_id>/."""

    _validate_consistency(summary, interpretation)
    run_directory = resolve_run_directory(output_directory, summary.run_metadata.run_id)
    present = {name for name in EXPECTED_CHARTS if (run_directory / name).is_file()}
    markdown = assemble_report_markdown(summary, interpretation, present_charts=present)
    path = write_report_markdown(markdown, run_directory)
    return ReportArtifact(
        run_id=summary.run_metadata.run_id,
        as_of_date=summary.run_metadata.as_of_date,
        path=path,
        interpretation_status=interpretation.status,
        missing_visualizations=tuple(
            name for name in EXPECTED_CHARTS if name not in present
        ),
    )


def generate_report_file(run_directory: str | Path) -> ReportArtifact:
    """Load validated run artifacts and write market_report.md beside them."""

    directory = Path(run_directory)
    quant_path = directory / "quant_summary.json"
    market_path = directory / "market_summary.json"
    if not quant_path.is_file():
        raise ReportError(f"missing quant summary: {quant_path}")
    if not market_path.is_file():
        raise ReportError(f"missing market summary: {market_path}")
    summary = QuantSummary.model_validate_json(quant_path.read_text(encoding="utf-8"))
    interpretation = MarketInterpretation.model_validate_json(
        market_path.read_text(encoding="utf-8")
    )
    if directory.name != summary.run_metadata.run_id:
        raise ReportError("output directory does not match run_id")
    return generate_report(summary, interpretation, output_directory=directory)
