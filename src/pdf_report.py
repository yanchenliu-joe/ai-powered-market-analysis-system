"""Deterministic PDF assembly from already-validated run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.display import (
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
from src.reporting import (
    EXPECTED_CHARTS,
    FALLBACK_DISCLAIMER,
    METHODOLOGY,
    UNAVAILABLE_INTERPRETATION_NOTE,
    _resolved_prose,
    _validate_consistency,
    ordered_sector_records,
    render_number,
    resolve_run_directory,
)
from src.schemas import InterpretationStatus, MarketInterpretation, QuantSummary

PDF_FILENAME = "market_report.pdf"
PDF_TEMP_FILENAME = ".market_report.pdf.tmp"

INK = colors.HexColor("#22261f")
MUTED = colors.HexColor("#5a5f56")
LINE = colors.HexColor("#cfc8b8")
SURFACE = colors.HexColor("#fffcf6")
HEADER_BG = colors.HexColor("#f3f1ea")


class PdfReportError(RuntimeError):
    """Raised when a PDF cannot be assembled from validated artifacts."""


@dataclass(frozen=True)
class PdfReportArtifact:
    run_id: str
    as_of_date: date
    path: Path
    included_charts: tuple[str, ...]


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PdfTitle",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "meta": ParagraphStyle(
            "PdfMeta",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
            textColor=MUTED,
            spaceAfter=2,
        ),
        "heading": ParagraphStyle(
            "PdfHeading",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=13,
            leading=16,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "PdfBody",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=14,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "PdfBullet",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
            textColor=INK,
            leftIndent=12,
            spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "PdfCaption",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceBefore=4,
            spaceAfter=10,
        ),
        "table": ParagraphStyle(
            "PdfTable",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=7.5,
            leading=9.5,
            textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "PdfTableHead",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=INK,
        ),
    }


def _bullets(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    flowables = [
        ListItem(Paragraph(_escape(item), styles["bullet"]), leftIndent=12)
        for item in items
    ]
    return ListFlowable(
        flowables,
        bulletType="bullet",
        start="•",
        leftIndent=16,
        bulletFontName="Times-Roman",
        bulletFontSize=10,
    )


def _chart_flowable(
    run_directory: Path,
    filename: str,
    caption: str,
    styles: dict[str, ParagraphStyle],
) -> list:
    path = run_directory / filename
    if not path.is_file():
        return [Paragraph("Visualization unavailable for this run.", styles["caption"])]
    try:
        image = Image(str(path))
        width, height = image.wrap(0, 0)
    except Exception:
        return [Paragraph("Visualization unavailable for this run.", styles["caption"])]
    max_width = 6.4 * inch
    max_height = 3.4 * inch
    if width <= 0 or height <= 0:
        return [Paragraph("Visualization unavailable for this run.", styles["caption"])]
    scale = min(max_width / width, max_height / height, 1)
    image.drawWidth = width * scale
    image.drawHeight = height * scale
    return [KeepTogether([image, Paragraph(_escape(caption), styles["caption"])])]


def _sector_table(summary: QuantSummary, styles: dict[str, ParagraphStyle]) -> Table:
    header = [
        Paragraph(label, styles["table_head"])
        for label in (
            "Sector",
            "Beta",
            "95% CI",
            "p-value",
            "Obs.",
            "+10bp",
            "Significance",
        )
    ]
    rows = [header]
    for record in ordered_sector_records(summary):
        rows.append(
            [
                Paragraph(_escape(record.ticker), styles["table"]),
                Paragraph(_escape(format_beta(record.beta_yield)), styles["table"]),
                Paragraph(
                    _escape(format_ci(record.ci_95_lower, record.ci_95_upper)),
                    styles["table"],
                ),
                Paragraph(_escape(format_p_value(record.p_value)), styles["table"]),
                Paragraph(_escape(render_number(record.n_obs)), styles["table"]),
                Paragraph(
                    _escape(format_effect_10bp(record.effect_10bp)), styles["table"]
                ),
                Paragraph(
                    _escape(display_sensitivity_label(record.sensitivity_label.value)),
                    styles["table"],
                ),
            ]
        )
    table = Table(
        rows,
        colWidths=[
            0.7 * inch,
            0.85 * inch,
            1.7 * inch,
            0.7 * inch,
            0.55 * inch,
            0.7 * inch,
            1.3 * inch,
        ],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
            ]
        )
    )
    return table


def _build_story(
    summary: QuantSummary,
    interpretation: MarketInterpretation,
    run_directory: Path,
    styles: dict[str, ParagraphStyle],
) -> tuple[list, tuple[str, ...]]:
    _validate_consistency(summary, interpretation)
    available = interpretation.status is InterpretationStatus.AVAILABLE
    as_of = summary.run_metadata.as_of_date.isoformat()
    run_id = summary.run_metadata.run_id
    generated = summary.run_metadata.generated_at.isoformat().replace("+00:00", "Z")
    breadth = summary.breadth
    trend = summary.trend
    quality = summary.data_quality
    included = tuple(
        name for name in EXPECTED_CHARTS if (run_directory / name).is_file()
    )

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

    story: list = [
        Paragraph("AI-Powered Market Analysis System", styles["title"]),
        Paragraph(f"As of: {as_of}", styles["meta"]),
        Paragraph(f"Run ID: {run_id}", styles["meta"]),
        Paragraph(f"Generated: {generated}", styles["meta"]),
        Paragraph(f"Status: {summary.status.value}", styles["meta"]),
        Spacer(1, 8),
        Paragraph("Executive Summary", styles["heading"]),
    ]
    if available and executive is not None:
        story.append(Paragraph(_escape(executive), styles["body"]))
        if interpretation.key_confirmed_signals:
            story.append(Paragraph("Confirmed signals", styles["caption"]))
            story.append(_bullets(list(interpretation.key_confirmed_signals), styles))
        if interpretation.risk_flags:
            story.append(Paragraph("Risk flags", styles["caption"]))
            story.append(_bullets(list(interpretation.risk_flags), styles))
    else:
        story.append(Paragraph(UNAVAILABLE_INTERPRETATION_NOTE, styles["body"]))

    story.extend(
        [
            Paragraph("Market Participation", styles["heading"]),
            _bullets(
                [
                    (
                        "% Above 50DMA: "
                        f"{format_breadth_percent(breadth.pct_above_50dma)}"
                    ),
                    (
                        "% Above 200DMA: "
                        f"{format_breadth_percent(breadth.pct_above_200dma)}"
                    ),
                    f"Advancers: {render_number(breadth.advancers)}",
                    f"Decliners: {render_number(breadth.decliners)}",
                    "Advance/Decline Ratio: "
                    f"{format_advance_decline_ratio(breadth.advance_decline_ratio)}",
                    "Breadth Momentum (20D): "
                    f"{format_breadth_momentum(breadth.breadth_momentum_20d)}",
                    f"Breadth status: {breadth.status.value}",
                ],
                styles,
            ),
        ]
    )
    if participation is not None:
        story.append(Paragraph(_escape(participation), styles["body"]))
    story.extend(
        _chart_flowable(
            run_directory,
            "breadth_timeseries.png",
            "Market breadth time series",
            styles,
        )
    )

    story.extend(
        [
            Paragraph("Trend Conditions", styles["heading"]),
            _bullets(
                [
                    f"Adjusted Close: {format_price(trend.adjusted_close)}",
                    f"SMA20: {format_price(trend.sma_20)}",
                    f"SMA50: {format_price(trend.sma_50)}",
                    f"SMA200: {format_price(trend.sma_200)}",
                    (
                        "Distance to SMA20: "
                        f"{format_distance_percent(trend.distance_to_sma_20)}"
                    ),
                    (
                        "Distance to SMA50: "
                        f"{format_distance_percent(trend.distance_to_sma_50)}"
                    ),
                    (
                        "Distance to SMA200: "
                        f"{format_distance_percent(trend.distance_to_sma_200)}"
                    ),
                    f"Trend regime: {display_trend_regime(trend.trend_regime.value)}",
                ],
                styles,
            ),
        ]
    )
    if trend_prose is not None:
        story.append(Paragraph(_escape(trend_prose), styles["body"]))
    story.extend(_chart_flowable(run_directory, "spy_trend.png", "SPY trend", styles))

    story.extend(
        [
            Paragraph("Sector Rate Sensitivity", styles["heading"]),
            Paragraph(
                "Yield unit: "
                f"{summary.run_metadata.yield_unit.replace('_', ' ')}. "
                "Sector yield coefficients describe statistical association "
                "and exposure, not causation.",
                styles["body"],
            ),
            _sector_table(summary, styles),
            Spacer(1, 8),
        ]
    )
    if sector_prose is not None:
        story.append(Paragraph(_escape(sector_prose), styles["body"]))
    story.extend(
        _chart_flowable(
            run_directory,
            "sector_rate_beta.png",
            "Sector rate sensitivity",
            styles,
        )
    )

    story.extend(
        [
            Paragraph("Data Quality", styles["heading"]),
            _bullets(
                [
                    "Available equity tickers / universe size: "
                    f"{quality.available_equity_tickers} / {quality.universe_size}",
                    f"Latest 50DMA valid count: {quality.latest_50dma_valid_count}",
                    f"Latest 200DMA valid count: {quality.latest_200dma_valid_count}",
                    "SPY observation coverage (cleaned / raw): "
                    f"{quality.spy_cleaned_row_count} / {quality.spy_raw_row_count}",
                    "DGS10 usable observation coverage (usable / raw): "
                    f"{quality.dgs10_usable_observation_count} / "
                    f"{quality.dgs10_raw_row_count}",
                    f"Available sectors: {quality.available_sector_tickers}",
                    f"Valid regressions: {quality.valid_sector_count}",
                    f"Insufficient regressions: {quality.insufficient_sector_count}",
                ],
                styles,
            ),
        ]
    )
    if quality.warnings:
        story.append(Paragraph("Warnings", styles["caption"]))
        story.append(_bullets(list(quality.warnings), styles))

    extra_limitations = unique_limitation_texts(
        [METHODOLOGY],
        list(summary.limitations),
        [risks_prose] if risks_prose else [],
        [
            "Yield changes are measured in percentage points. A move from "
            "4.30 to 4.35 is 0.05, not 0.0005."
        ],
    )[1:]
    story.extend(
        [
            Paragraph("Methodology and Limitations", styles["heading"]),
            Paragraph(_escape(METHODOLOGY.rstrip()), styles["body"]),
        ]
    )
    if extra_limitations:
        story.append(Paragraph("Additional validated limitations", styles["caption"]))
        story.append(_bullets(extra_limitations, styles))

    disclaimer = FALLBACK_DISCLAIMER
    if available and interpretation.disclaimer and interpretation.disclaimer.strip():
        disclaimer = interpretation.disclaimer
    story.extend(
        [
            Paragraph("Disclaimer", styles["heading"]),
            Paragraph(_escape(disclaimer), styles["body"]),
        ]
    )
    return story, included


def write_report_pdf(
    story: list, destination: Path, *, run_id: str, as_of: str
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / PDF_TEMP_FILENAME

    def _footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(MUTED)
        canvas.setFont("Times-Roman", 8)
        canvas.drawString(
            inch,
            0.45 * inch,
            f"Run {run_id}  ·  As of {as_of}  ·  Research and education only",
        )
        canvas.drawRightString(letter[0] - inch, 0.45 * inch, str(doc.page))
        canvas.restoreState()

    try:
        document = SimpleDocTemplate(
            str(temporary),
            pagesize=letter,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.7 * inch,
            bottomMargin=0.7 * inch,
            title="AI-Powered Market Analysis Report",
            author="AI-Powered Market Analysis System",
        )
        document.build(story, onFirstPage=_footer, onLaterPages=_footer)
        temporary.replace(destination)
    except (OSError, ValueError, RuntimeError) as error:
        temporary.unlink(missing_ok=True)
        raise PdfReportError(f"unable to write PDF: {destination}") from error
    return destination


def generate_pdf_report(
    summary: QuantSummary,
    interpretation: MarketInterpretation,
    *,
    output_directory: str | Path,
) -> PdfReportArtifact:
    """Write outputs/<run_id>/market_report.pdf from validated objects."""

    run_directory = resolve_run_directory(output_directory, summary.run_metadata.run_id)
    styles = _styles()
    story, included = _build_story(summary, interpretation, run_directory, styles)
    path = write_report_pdf(
        story,
        run_directory / PDF_FILENAME,
        run_id=summary.run_metadata.run_id,
        as_of=summary.run_metadata.as_of_date.isoformat(),
    )
    return PdfReportArtifact(
        run_id=summary.run_metadata.run_id,
        as_of_date=summary.run_metadata.as_of_date,
        path=path,
        included_charts=included,
    )


def generate_pdf_from_run_directory(run_directory: str | Path) -> PdfReportArtifact:
    """Load validated JSON artifacts and write market_report.pdf beside them."""

    directory = Path(run_directory)
    quant_path = directory / "quant_summary.json"
    market_path = directory / "market_summary.json"
    if not quant_path.is_file():
        raise PdfReportError(f"missing quant summary: {quant_path}")
    if not market_path.is_file():
        raise PdfReportError(f"missing market summary: {market_path}")
    summary = QuantSummary.model_validate_json(quant_path.read_text(encoding="utf-8"))
    interpretation = MarketInterpretation.model_validate_json(
        market_path.read_text(encoding="utf-8")
    )
    return generate_pdf_report(summary, interpretation, output_directory=directory)
