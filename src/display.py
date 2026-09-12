"""Human-readable presentation helpers. No quantitative recalculation."""

from __future__ import annotations

from src.schemas import SensitivityLabel, TrendRegime

UNAVAILABLE = "Unavailable"

TREND_REGIME_DISPLAY: dict[str, str] = {
    TrendRegime.STRONG_UPTREND.value: "Strong Uptrend",
    TrendRegime.UPTREND.value: "Uptrend",
    TrendRegime.TRANSITION.value: "Transition",
    TrendRegime.DOWNTREND.value: "Downtrend",
    TrendRegime.STRONG_DOWNTREND.value: "Strong Downtrend",
    TrendRegime.INSUFFICIENT_DATA.value: "Insufficient Data",
}

SENSITIVITY_LABEL_DISPLAY: dict[str, str] = {
    SensitivityLabel.NEGATIVE_SIGNIFICANT.value: "Negative — Significant",
    SensitivityLabel.NEGATIVE_NOT_SIGNIFICANT.value: "Negative — Not Significant",
    SensitivityLabel.POSITIVE_SIGNIFICANT.value: "Positive — Significant",
    SensitivityLabel.POSITIVE_NOT_SIGNIFICANT.value: "Positive — Not Significant",
    SensitivityLabel.INSUFFICIENT_DATA.value: "Insufficient Data",
}

SECTOR_DISPLAY_NAMES: dict[str, str] = {
    "XLC": "XLC — Communication Services",
    "XLY": "XLY — Consumer Discretionary",
    "XLP": "XLP — Consumer Staples",
    "XLE": "XLE — Energy",
    "XLF": "XLF — Financials",
    "XLV": "XLV — Health Care",
    "XLI": "XLI — Industrials",
    "XLK": "XLK — Technology",
    "XLB": "XLB — Materials",
    "XLRE": "XLRE — Real Estate",
    "XLU": "XLU — Utilities",
}


def display_trend_regime(value: str) -> str:
    return TREND_REGIME_DISPLAY.get(value, value)


def display_sensitivity_label(value: str) -> str:
    return SENSITIVITY_LABEL_DISPLAY.get(value, value)


def display_sector_name(ticker: str) -> str:
    return SECTOR_DISPLAY_NAMES.get(ticker, ticker)


def format_breadth_percent(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value:.1f}%"


def format_breadth_momentum(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value:.1f} percentage points"


def format_advance_decline_ratio(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value:.2f}"


def format_price(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    return f"${value:.2f}"


def format_distance_percent(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value * 100:+.2f}%"


def format_beta(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value:.4f}"


def format_beta_annotation(value: float) -> str:
    return f"{value:+.3f}"


def format_ci(lower: float | None, upper: float | None) -> str:
    if lower is None or upper is None:
        return UNAVAILABLE
    return f"[{format_beta(lower)}, {format_beta(upper)}]"


def format_p_value(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def format_effect_10bp(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value * 100:+.2f}%"


def limitation_semantic_keys(text: str) -> set[str]:
    """Stable keys for exact/semantic-key limitation deduplication."""

    normalized = " ".join(text.lower().split())
    keys: set[str] = set()
    if "survivorship" in normalized:
        keys.add("survivorship")
    if "association" in normalized and "causation" in normalized:
        keys.add("association")
    if "omit" in normalized and "factor" in normalized:
        keys.add("omitted_factors")
    if "percentage point" in normalized or "percentage-point" in normalized:
        keys.add("yield_units")
    return keys or {normalized}


def unique_limitation_texts(*groups: list[str]) -> list[str]:
    """Keep the first occurrence of each semantic key or normalized string."""

    seen: set[str] = set()
    unique: list[str] = []
    for group in groups:
        for item in group:
            stripped = item.strip()
            if not stripped:
                continue
            keys = limitation_semantic_keys(stripped)
            if keys <= seen:
                continue
            seen.update(keys)
            unique.append(stripped)
    return unique
