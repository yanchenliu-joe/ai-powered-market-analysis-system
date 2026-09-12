"""Headless deterministic tests for the three Phase 7 charts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from src.schemas import QuantSummary, SectorRegressionSummary
from src.visualization import (
    CHART_DPI,
    EXPECTED_SECTORS,
    VisualizationError,
    build_breadth_figure,
    build_sector_beta_figure,
    build_trend_figure,
    generate_all_visualizations,
    generate_breadth_chart,
)


def breadth_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=5)[::-1],
            "pct_above_50dma": [70.0, np.nan, 60.0, 55.0, 50.0],
            "pct_above_200dma": [52.0, 51.0, np.nan, 49.0, 48.0],
        }
    )


def trend_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=5),
            "adjusted_close": [470.0, 472.0, 471.0, 474.0, 475.0],
            "sma_20": [np.nan, np.nan, 469.0, 470.0, 471.0],
            "sma_50": [np.nan, np.nan, np.nan, 468.0, 469.0],
            "sma_200": [np.nan, np.nan, np.nan, np.nan, 450.0],
            "trend_regime": [
                "insufficient_data",
                "insufficient_data",
                "insufficient_data",
                "insufficient_data",
                "strong_uptrend",
            ],
        }
    )


def sector_results(
    *,
    all_insufficient: bool = False,
) -> list[SectorRegressionSummary]:
    results = []
    for index, ticker in enumerate(EXPECTED_SECTORS):
        insufficient = all_insufficient or index == len(EXPECTED_SECTORS) - 1
        if insufficient:
            results.append(
                SectorRegressionSummary(
                    ticker=ticker,
                    alpha=None,
                    beta_yield=None,
                    beta_std_error=None,
                    beta_t_value=None,
                    p_value=None,
                    ci_95_lower=None,
                    ci_95_upper=None,
                    r_squared=None,
                    adjusted_r_squared=None,
                    n_obs=150,
                    start_date=date(2023, 1, 2),
                    end_date=date(2023, 8, 1),
                    effect_10bp=None,
                    sensitivity_label="insufficient_data",
                    status="insufficient_data",
                    error_reason="not enough observations",
                )
            )
            continue
        beta = (0.01 + index * 0.002) * (1 if index % 2 == 0 else -1)
        significant = index % 3 == 0
        direction = "positive" if beta > 0 else "negative"
        label = (
            f"{direction}_significant"
            if significant
            else f"{direction}_not_significant"
        )
        results.append(
            SectorRegressionSummary(
                ticker=ticker,
                alpha=0.001,
                beta_yield=beta,
                beta_std_error=0.002,
                beta_t_value=beta / 0.002,
                p_value=0.01 if significant else 0.20,
                ci_95_lower=beta - 0.005,
                ci_95_upper=beta + 0.005,
                r_squared=0.2,
                adjusted_r_squared=0.19,
                n_obs=252,
                start_date=date(2023, 1, 2),
                end_date=date(2023, 12, 29),
                effect_10bp=beta * 0.10,
                sensitivity_label=label,
                status="success",
                error_reason=None,
            )
        )
    return results


def quant_summary() -> QuantSummary:
    records = sector_results()
    return QuantSummary.model_validate(
        {
            "schema_version": "1.0.0",
            "run_metadata": {
                "run_id": "visual-test-run",
                "as_of_date": date(2024, 1, 8),
                "generated_at": datetime(2024, 1, 9, 12, 0, tzinfo=UTC),
                "schema_version": "1.0.0",
                "analysis_start": date(2023, 1, 2),
                "analysis_end": date(2024, 1, 8),
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
                "requested_end": date(2024, 1, 8),
                "equity_raw_row_count": 1000,
                "equity_cleaned_row_count": 1000,
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
                "sector_result_count": 11,
                "valid_sector_count": 10,
                "insufficient_sector_count": 1,
                "exclusions": [],
                "warnings": [],
            },
            "breadth": {
                "as_of_date": date(2024, 1, 8),
                "pct_above_50dma": 70.0,
                "above_50dma_count": 2,
                "valid_count_50dma": 3,
                "pct_above_200dma": 52.0,
                "above_200dma_count": 2,
                "valid_count_200dma": 3,
                "advancers": 2,
                "decliners": 1,
                "valid_return_count": 3,
                "advance_decline_ratio": 2.0,
                "net_advances": 1,
                "breadth_momentum_20d": 5.0,
                "status": "available",
                "unavailable_fields": [],
            },
            "trend": {
                "as_of_date": date(2024, 1, 8),
                "adjusted_close": 475.0,
                "sma_20": 471.0,
                "sma_50": 469.0,
                "sma_200": 450.0,
                "distance_to_sma_20": 475 / 471 - 1,
                "distance_to_sma_50": 475 / 469 - 1,
                "distance_to_sma_200": 475 / 450 - 1,
                "trend_regime": "strong_uptrend",
            },
            "sector_regressions": records,
            "limitations": ["Association is not causation."],
            "status": "partial",
        }
    )


def test_agg_backend_is_active() -> None:
    assert "agg" in matplotlib.get_backend().lower()


def test_breadth_figure_uses_both_precomputed_series_and_fixed_axis() -> None:
    chart = build_breadth_figure(breadth_data())
    try:
        series = {
            line.get_label(): np.asarray(line.get_ydata(), dtype=float)
            for line in chart.axes.lines
            if line.get_label() in {"Above 50-day SMA", "Above 200-day SMA"}
        }
        reference = [
            line
            for line in chart.axes.lines
            if np.allclose(np.asarray(line.get_ydata(), dtype=float), 50)
        ]
        texts = [text.get_text() for text in chart.axes.texts]

        assert list(series) == ["Above 50-day SMA", "Above 200-day SMA"]
        assert chart.axes.get_ylim() == pytest.approx((0, 100))
        assert np.isnan(series["Above 50-day SMA"]).any()
        assert np.isnan(series["Above 200-day SMA"]).any()
        assert "2024-01-08" in chart.axes.get_title()
        assert "S&P 500 Market Breadth" in chart.axes.get_title()
        assert chart.status == "success"
        assert reference
        assert "50DMA: 70.0%" in texts
        assert "200DMA: 52.0%" in texts
    finally:
        plt.close(chart.figure)


@pytest.mark.parametrize(
    "invalid_data",
    [
        pd.DataFrame({"date": ["2024-01-02"]}),
        pd.DataFrame(
            {
                "date": ["2024-01-02"],
                "pct_above_50dma": [101.0],
                "pct_above_200dma": [50.0],
            }
        ),
    ],
)
def test_breadth_input_contract_is_validated(
    invalid_data: pd.DataFrame,
) -> None:
    with pytest.raises(VisualizationError):
        build_breadth_figure(invalid_data)


def test_fully_insufficient_breadth_draws_message_not_zero_lines() -> None:
    data = breadth_data()
    data[["pct_above_50dma", "pct_above_200dma"]] = np.nan

    chart = build_breadth_figure(data)
    try:
        assert chart.status == "insufficient_data"
        assert len(chart.axes.lines) == 0
        assert any("Insufficient data" in text.get_text() for text in chart.axes.texts)
    finally:
        plt.close(chart.figure)


def test_trend_figure_uses_precomputed_price_and_smas_with_gaps() -> None:
    chart = build_trend_figure(trend_data())
    try:
        lines = {line.get_label(): line for line in chart.axes.lines}

        assert list(lines) == [
            "SPY adjusted close",
            "20-day SMA",
            "50-day SMA",
            "200-day SMA",
        ]
        assert np.isnan(lines["20-day SMA"].get_ydata()).any()
        assert np.isnan(lines["50-day SMA"].get_ydata()).any()
        assert np.isnan(lines["200-day SMA"].get_ydata()).any()
        valid_sma_20 = np.asarray(lines["20-day SMA"].get_ydata())
        valid_sma_20 = valid_sma_20[~np.isnan(valid_sma_20)]
        assert (valid_sma_20 != 0).all()
        assert "Strong Uptrend" in chart.axes.get_title()
        assert "strong_uptrend" not in chart.axes.get_title()
        assert trend_data()["trend_regime"].iloc[-1] == "strong_uptrend"
        assert "2024-01-08" in chart.axes.get_title()
        assert any(text.get_text() == "SPY: $475.00" for text in chart.axes.texts)
    finally:
        plt.close(chart.figure)


def test_trend_required_columns_and_regimes_are_validated() -> None:
    missing = trend_data().drop(columns="sma_200")
    invalid_regime = trend_data()
    invalid_regime.loc[invalid_regime.index[-1], "trend_regime"] = "bullish"

    with pytest.raises(VisualizationError, match="missing"):
        build_trend_figure(missing)
    with pytest.raises(VisualizationError, match="unsupported"):
        build_trend_figure(invalid_regime)


def test_sector_chart_preserves_order_values_intervals_and_significance() -> None:
    records = sector_results()
    chart = build_sector_beta_figure(records, date(2024, 1, 8))
    try:
        tick_labels = [label.get_text() for label in chart.axes.get_yticklabels()]
        widths = [patch.get_width() for patch in chart.axes.patches]
        valid_betas = [
            record.beta_yield for record in records if record.beta_yield is not None
        ]
        interval_segments = [
            segment
            for collection in chart.axes.collections
            for segment in collection.get_segments()
            if len(segment) == 2
        ]

        assert [label[: label.index(" — ")] for label in tick_labels] == list(
            EXPECTED_SECTORS
        )
        assert all(
            ticker in label
            for ticker, label in zip(EXPECTED_SECTORS, tick_labels, strict=True)
        )
        assert widths == pytest.approx(valid_betas)
        assert len(widths) == 10
        assert any(
            np.allclose(
                segment[:, 0], [-0.005 + valid_betas[0], 0.005 + valid_betas[0]]
            )
            for segment in interval_segments
        )
        assert (
            chart.axes.patches[0].get_facecolor()
            != chart.axes.patches[1].get_facecolor()
        )
        assert any("Insufficient data" in text.get_text() for text in chart.axes.texts)
        assert "percentage-point" in chart.axes.get_xlabel()
        assert "Statistical association" in chart.axes.get_title()
        texts = [text.get_text() for text in chart.axes.texts]
        assert f"{valid_betas[0]:+.3f}" in texts
        assert "+0.000" not in texts
        assert "-0.000" not in texts
        assert "0.000" not in texts
    finally:
        plt.close(chart.figure)


def test_sector_chart_has_zero_reference_and_no_zero_beta_for_insufficient() -> None:
    chart = build_sector_beta_figure(sector_results(), date(2024, 1, 8))
    try:
        vertical_lines = [
            line
            for line in chart.axes.lines
            if np.array_equal(np.asarray(line.get_xdata()), np.array([0, 0]))
        ]

        assert vertical_lines
        assert len(chart.axes.patches) == 10
        assert all(patch.get_width() != 0 for patch in chart.axes.patches)
        texts = [text.get_text() for text in chart.axes.texts]
        assert "Insufficient data" in texts
        assert "+0.000" not in texts
        assert "-0.000" not in texts
    finally:
        plt.close(chart.figure)


def test_all_insufficient_sectors_remain_labeled_without_bars() -> None:
    chart = build_sector_beta_figure(
        sector_results(all_insufficient=True), date(2024, 1, 8)
    )
    try:
        assert chart.status == "insufficient_data"
        assert len(chart.axes.patches) == 0
        tickers_from_labels = [
            label.get_text().split(" — ", 1)[0]
            for label in chart.axes.get_yticklabels()
        ]
        assert tickers_from_labels == list(EXPECTED_SECTORS)
        assert all(
            ticker in label.get_text()
            for ticker, label in zip(
                EXPECTED_SECTORS, chart.axes.get_yticklabels(), strict=True
            )
        )
        assert (
            sum("Insufficient data" in text.get_text() for text in chart.axes.texts)
            >= 11
        )
    finally:
        plt.close(chart.figure)


def test_sector_order_contract_is_enforced() -> None:
    reversed_records = list(reversed(sector_results()))

    with pytest.raises(VisualizationError, match="project order"):
        build_sector_beta_figure(reversed_records, date(2024, 1, 8))


def test_generate_all_creates_exact_nonempty_160dpi_files_and_closes_figures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_dpi: list[int] = []
    original_savefig = Figure.savefig

    def capture_savefig(self: Figure, *args: object, **kwargs: object) -> None:
        captured_dpi.append(kwargs["dpi"])  # type: ignore[arg-type]
        original_savefig(self, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture_savefig)
    figures_before = set(plt.get_fignums())

    artifacts = generate_all_visualizations(
        breadth_data(), trend_data(), quant_summary(), tmp_path
    )

    assert [artifact.output_path.name for artifact in artifacts] == [
        "breadth_timeseries.png",
        "spy_trend.png",
        "sector_rate_beta.png",
    ]
    assert all(
        artifact.output_path.parent == tmp_path / "visual-test-run"
        for artifact in artifacts
    )
    assert all(
        artifact.output_path.is_file() and artifact.output_path.stat().st_size > 0
        for artifact in artifacts
    )
    assert captured_dpi == [CHART_DPI, CHART_DPI, CHART_DPI]
    assert CHART_DPI >= 150
    assert set(plt.get_fignums()) == figures_before


def test_individual_generator_creates_run_directory_and_exact_name(
    tmp_path: Path,
) -> None:
    run_directory = tmp_path / "individual-run"

    artifact = generate_breadth_chart(breadth_data(), run_directory)

    assert artifact.output_path == run_directory / "breadth_timeseries.png"
    assert artifact.output_path.stat().st_size > 0
    assert artifact.as_of_date == "2024-01-08"


def test_missing_latest_breadth_value_is_not_invented() -> None:
    data = breadth_data()
    data["pct_above_50dma"] = np.nan
    chart = build_breadth_figure(data)
    try:
        texts = [text.get_text() for text in chart.axes.texts]
        latest_200 = (
            data.sort_values("date").dropna(subset=["pct_above_200dma"]).iloc[-1]
        )
        assert not any(text.startswith("50DMA:") for text in texts)
        assert f"200DMA: {float(latest_200['pct_above_200dma']):.1f}%" in texts
    finally:
        plt.close(chart.figure)


def test_visualization_source_contains_no_quantitative_or_external_calls() -> None:
    source = (Path(__file__).parents[1] / "src" / "visualization.py").read_text(
        encoding="utf-8"
    )

    for forbidden in (
        ".rolling(",
        ".pct_change(",
        "sm.OLS",
        "yfinance",
        "pandas_datareader",
        "openai",
        "src.breadth",
        "src.trend",
        "src.regression",
        "compute_breadth",
        "compute_trend",
        "run_sector_regressions",
    ):
        assert forbidden not in source
