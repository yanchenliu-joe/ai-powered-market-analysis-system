"""Headless charts built exclusively from accepted quantitative outputs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from src.display import (
    display_sector_name,
    display_trend_regime,
    format_beta_annotation,
    format_breadth_percent,
    format_price,
)
from src.schemas import (
    QuantSummary,
    RegressionStatus,
    SectorRegressionSummary,
    SensitivityLabel,
    TrendRegime,
)

CHART_DPI = 160
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


class VisualizationError(RuntimeError):
    """Raised when a chart input or output violates its contract."""


@dataclass(frozen=True)
class BuiltChart:
    """Open figure plus deterministic metadata for inspection and saving."""

    figure: Figure
    axes: Axes
    as_of_date: str | None
    status: Literal["success", "insufficient_data"]


@dataclass(frozen=True)
class ChartArtifact:
    """Metadata for one saved PNG artifact."""

    chart_name: str
    output_path: Path
    as_of_date: str | None
    status: Literal["success", "insufficient_data"]


def _new_figure(figsize: tuple[float, float]) -> tuple[Figure, Axes]:
    with sns.axes_style("whitegrid"):
        return plt.subplots(figsize=figsize, constrained_layout=True)


def _normalize_dates(data: pd.DataFrame) -> pd.DataFrame:
    normalized = data.copy()
    try:
        normalized["date"] = (
            pd.to_datetime(normalized["date"], errors="raise", utc=True)
            .dt.tz_localize(None)
            .dt.normalize()
        )
    except (KeyError, TypeError, ValueError) as error:
        raise VisualizationError("chart dates are missing or invalid") from error
    if normalized["date"].duplicated().any():
        raise VisualizationError("chart data contains duplicate dates")
    return normalized.sort_values("date", ignore_index=True)


def _validate_numeric_series(
    data: pd.DataFrame,
    columns: Sequence[str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    for column in columns:
        if column not in data:
            raise VisualizationError(f"chart data is missing column: {column}")
        numeric = pd.to_numeric(data[column], errors="coerce")
        invalid = numeric.isna() & data[column].notna()
        if invalid.any():
            raise VisualizationError(f"{column} contains nonnumeric values")
        finite = numeric.dropna().to_numpy(dtype=float)
        if not np.isfinite(finite).all():
            raise VisualizationError(f"{column} contains Infinity")
        if minimum is not None and (numeric.dropna() < minimum).any():
            raise VisualizationError(f"{column} is below {minimum}")
        if maximum is not None and (numeric.dropna() > maximum).any():
            raise VisualizationError(f"{column} exceeds {maximum}")


def _format_date_axis(axes: Axes) -> None:
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    axes.xaxis.set_major_locator(locator)
    axes.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))


def _insufficient_message(axes: Axes) -> None:
    axes.text(
        0.5,
        0.5,
        "Insufficient data for this visualization",
        transform=axes.transAxes,
        ha="center",
        va="center",
        fontsize=12,
        color="#5B6472",
    )


def _latest_valid_point(
    data: pd.DataFrame, column: str
) -> tuple[pd.Timestamp, float] | None:
    valid = data.loc[data[column].notna(), ["date", column]]
    if valid.empty:
        return None
    row = valid.iloc[-1]
    return row["date"], float(row[column])


def _annotate_latest_breadth(axes: Axes, breadth: pd.DataFrame) -> None:
    latest_50 = _latest_valid_point(breadth, "pct_above_50dma")
    latest_200 = _latest_valid_point(breadth, "pct_above_200dma")
    offsets = {
        "pct_above_50dma": (8, 10),
        "pct_above_200dma": (8, -14),
    }
    if latest_50 is not None and latest_200 is not None:
        if abs(latest_50[1] - latest_200[1]) < 6:
            offsets["pct_above_200dma"] = (8, -18)
    if latest_50 is not None:
        date, value = latest_50
        axes.annotate(
            f"50DMA: {format_breadth_percent(value)}",
            xy=(date, value),
            xytext=offsets["pct_above_50dma"],
            textcoords="offset points",
            fontsize=8,
            color="#2563EB",
        )
    if latest_200 is not None:
        date, value = latest_200
        axes.annotate(
            f"200DMA: {format_breadth_percent(value)}",
            xy=(date, value),
            xytext=offsets["pct_above_200dma"],
            textcoords="offset points",
            fontsize=8,
            color="#D97706",
        )


def build_breadth_figure(breadth_timeseries: pd.DataFrame) -> BuiltChart:
    """Build market-breadth lines from precomputed participation fields."""

    required = ["date", "pct_above_50dma", "pct_above_200dma"]
    missing = [column for column in required if column not in breadth_timeseries]
    if missing:
        raise VisualizationError(
            f"breadth data is missing columns: {', '.join(missing)}"
        )
    if breadth_timeseries.empty:
        raise VisualizationError("breadth data must not be empty")
    breadth = _normalize_dates(breadth_timeseries.loc[:, required])
    series_columns = ["pct_above_50dma", "pct_above_200dma"]
    _validate_numeric_series(breadth, series_columns, minimum=0, maximum=100)

    as_of_date = breadth["date"].iloc[-1].date().isoformat()
    figure, axes = _new_figure((10.5, 5.5))
    colors = {"pct_above_50dma": "#2563EB", "pct_above_200dma": "#D97706"}
    labels = {
        "pct_above_50dma": "Above 50-day SMA",
        "pct_above_200dma": "Above 200-day SMA",
    }
    usable = False
    for column in series_columns:
        if breadth[column].notna().any():
            axes.plot(
                breadth["date"],
                breadth[column],
                color=colors[column],
                linewidth=2,
                label=labels[column],
            )
            usable = True

    axes.set_ylim(0, 100)
    axes.set_xlabel("Date")
    axes.set_ylabel("Valid constituents above moving average (%)")
    axes.set_title(
        "S&P 500 Market Breadth\n"
        f"% of Valid Constituents Above Moving Averages\nAs of {as_of_date}"
    )
    _format_date_axis(axes)
    if usable:
        axes.axhline(
            50,
            color="#9CA3AF",
            linewidth=1,
            linestyle=":",
            zorder=0,
            label="_nolegend_",
        )
        _annotate_latest_breadth(axes, breadth)
        axes.legend(loc="best", frameon=True)
    else:
        _insufficient_message(axes)
    return BuiltChart(
        figure=figure,
        axes=axes,
        as_of_date=as_of_date,
        status="success" if usable else "insufficient_data",
    )


def build_trend_figure(trend_timeseries: pd.DataFrame) -> BuiltChart:
    """Build SPY price/SMA lines without calculating any moving average."""

    required = [
        "date",
        "adjusted_close",
        "sma_20",
        "sma_50",
        "sma_200",
        "trend_regime",
    ]
    missing = [column for column in required if column not in trend_timeseries]
    if missing:
        raise VisualizationError(f"trend data is missing columns: {', '.join(missing)}")
    if trend_timeseries.empty:
        raise VisualizationError("trend data must not be empty")
    trend = _normalize_dates(trend_timeseries.loc[:, required])
    numeric_columns = ["adjusted_close", "sma_20", "sma_50", "sma_200"]
    _validate_numeric_series(trend, numeric_columns, minimum=0)
    invalid_regimes = set(trend["trend_regime"].dropna()) - {
        regime.value for regime in TrendRegime
    }
    if invalid_regimes:
        raise VisualizationError("trend data contains an unsupported regime")

    as_of_date = trend["date"].iloc[-1].date().isoformat()
    latest_regime = str(trend["trend_regime"].iloc[-1])
    figure, axes = _new_figure((10.5, 5.5))
    styles = {
        "adjusted_close": ("SPY adjusted close", "#111827", 2.4, "-"),
        "sma_20": ("20-day SMA", "#2563EB", 1.6, "-"),
        "sma_50": ("50-day SMA", "#D97706", 1.7, "--"),
        "sma_200": ("200-day SMA", "#7C3AED", 1.8, "-."),
    }
    usable = False
    for column, (label, color, width, linestyle) in styles.items():
        if trend[column].notna().any():
            axes.plot(
                trend["date"],
                trend[column],
                label=label,
                color=color,
                linewidth=width,
                linestyle=linestyle,
            )
            usable = True

    axes.set_xlabel("Date")
    axes.set_ylabel("SPY adjusted price (USD)")
    axes.set_title(
        "SPY Price and Moving-Average Trend Structure\n"
        f"As of {as_of_date} · Regime: {display_trend_regime(latest_regime)}"
    )
    _format_date_axis(axes)
    if usable:
        latest_price = _latest_valid_point(trend, "adjusted_close")
        if latest_price is not None:
            date, value = latest_price
            axes.annotate(
                f"SPY: {format_price(value)}",
                xy=(date, value),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=8,
                color="#111827",
            )
        axes.legend(loc="best", frameon=True)
    else:
        _insufficient_message(axes)
    return BuiltChart(
        figure=figure,
        axes=axes,
        as_of_date=as_of_date,
        status="success" if usable else "insufficient_data",
    )


def build_sector_beta_figure(
    sector_results: Sequence[SectorRegressionSummary],
    as_of_date: date,
) -> BuiltChart:
    """Build ordered sector beta estimates and accepted 95% intervals."""

    records = list(sector_results)
    tickers = tuple(record.ticker for record in records)
    if tickers != EXPECTED_SECTORS:
        raise VisualizationError(
            "sector results must contain all 11 sectors in project order"
        )

    figure, axes = _new_figure((10.5, 7.0))
    positions = np.arange(len(records))
    valid_records = [
        (position, record)
        for position, record in zip(positions, records, strict=True)
        if record.status == RegressionStatus.SUCCESS
    ]
    for position, record in valid_records:
        assert record.beta_yield is not None
        assert record.ci_95_lower is not None
        assert record.ci_95_upper is not None
        lower_error = record.beta_yield - record.ci_95_lower
        upper_error = record.ci_95_upper - record.beta_yield
        if lower_error < 0 or upper_error < 0:
            raise VisualizationError(
                f"{record.ticker} confidence interval does not contain beta"
            )
        significant = record.sensitivity_label in {
            SensitivityLabel.POSITIVE_SIGNIFICANT,
            SensitivityLabel.NEGATIVE_SIGNIFICANT,
        }
        color = "#2563EB" if significant else "#9CA3AF"
        axes.barh(
            position,
            record.beta_yield,
            height=0.62,
            color=color,
            edgecolor="#374151",
            linewidth=0.6,
        )
        axes.errorbar(
            record.beta_yield,
            position,
            xerr=np.array([[lower_error], [upper_error]]),
            fmt="none",
            ecolor="#111827",
            elinewidth=1.2,
            capsize=3,
        )
        offset = 0.004 if record.beta_yield >= 0 else -0.004
        axes.text(
            record.beta_yield + offset,
            position,
            format_beta_annotation(record.beta_yield),
            va="center",
            ha="left" if record.beta_yield >= 0 else "right",
            fontsize=8,
            color="#111827",
        )

    for position, record in zip(positions, records, strict=True):
        if record.status == RegressionStatus.INSUFFICIENT_DATA:
            axes.text(
                0.02,
                position,
                "Insufficient data",
                transform=axes.get_yaxis_transform(),
                va="center",
                color="#6B7280",
                fontsize=9,
            )

    axes.axvline(0, color="#111827", linewidth=1, linestyle="--")
    display_labels = [display_sector_name(ticker) for ticker in tickers]
    axes.set_yticks(positions, display_labels)
    if valid_records:
        values = [record.beta_yield for _, record in valid_records]
        span = max(abs(min(values)), abs(max(values)), 0.05)
        axes.set_xlim(-span * 1.35, span * 1.35)
    axes.invert_yaxis()
    axes.set_xlabel("Return sensitivity per +1 percentage-point change in 10Y yield")
    axes.set_ylabel("Sector ETF")
    iso_date = as_of_date.isoformat()
    axes.set_title(
        "Sector Rate-Sensitivity Estimates with 95% Confidence Intervals\n"
        f"Statistical association · As of {iso_date}"
    )
    axes.legend(
        handles=[
            Patch(facecolor="#2563EB", label="Significant"),
            Patch(facecolor="#9CA3AF", label="Not significant"),
            Patch(facecolor="none", edgecolor="none", label="Insufficient data"),
        ],
        loc="best",
        frameon=True,
    )
    if not valid_records:
        _insufficient_message(axes)
    return BuiltChart(
        figure=figure,
        axes=axes,
        as_of_date=iso_date,
        status="success" if valid_records else "insufficient_data",
    )


def _save_chart(
    chart: BuiltChart,
    run_directory: str | Path,
    filename: str,
) -> ChartArtifact:
    directory = Path(run_directory)
    destination = directory / filename
    temporary = directory / f".{Path(filename).stem}.tmp.png"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        chart.figure.savefig(
            temporary,
            format="png",
            dpi=CHART_DPI,
            bbox_inches="tight",
        )
        temporary.replace(destination)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise VisualizationError(f"unable to save chart: {destination}") from error
    finally:
        plt.close(chart.figure)
    return ChartArtifact(
        chart_name=Path(filename).stem,
        output_path=destination,
        as_of_date=chart.as_of_date,
        status=chart.status,
    )


def generate_breadth_chart(
    breadth_timeseries: pd.DataFrame, run_directory: str | Path
) -> ChartArtifact:
    return _save_chart(
        build_breadth_figure(breadth_timeseries),
        run_directory,
        "breadth_timeseries.png",
    )


def generate_trend_chart(
    trend_timeseries: pd.DataFrame, run_directory: str | Path
) -> ChartArtifact:
    return _save_chart(
        build_trend_figure(trend_timeseries),
        run_directory,
        "spy_trend.png",
    )


def generate_sector_beta_chart(
    sector_results: Sequence[SectorRegressionSummary],
    as_of_date: date,
    run_directory: str | Path,
) -> ChartArtifact:
    return _save_chart(
        build_sector_beta_figure(sector_results, as_of_date),
        run_directory,
        "sector_rate_beta.png",
    )


def generate_all_visualizations(
    breadth_timeseries: pd.DataFrame,
    trend_timeseries: pd.DataFrame,
    quant_summary: QuantSummary,
    output_directory: str | Path,
) -> list[ChartArtifact]:
    """Generate exactly the three required PNGs in outputs/<run_id>/."""

    run_directory = Path(output_directory) / quant_summary.run_metadata.run_id
    return [
        generate_breadth_chart(breadth_timeseries, run_directory),
        generate_trend_chart(trend_timeseries, run_directory),
        generate_sector_beta_chart(
            quant_summary.sector_regressions,
            quant_summary.run_metadata.as_of_date,
            run_directory,
        ),
    ]
