import type { SensitivityLabel, TrendRegime } from "@/types/market";

export const UNAVAILABLE = "Unavailable";

const TREND_REGIME_DISPLAY: Record<TrendRegime, string> = {
  strong_uptrend: "Strong Uptrend",
  uptrend: "Uptrend",
  transition: "Transition",
  downtrend: "Downtrend",
  strong_downtrend: "Strong Downtrend",
  insufficient_data: "Insufficient Data",
};

const SENSITIVITY_DISPLAY: Record<SensitivityLabel, string> = {
  negative_significant: "Negative · Significant",
  negative_not_significant: "Negative · Not Significant",
  positive_significant: "Positive · Significant",
  positive_not_significant: "Positive · Not Significant",
  insufficient_data: "Insufficient Data",
};

export function displayTrendRegime(value: string): string {
  return TREND_REGIME_DISPLAY[value as TrendRegime] ?? value;
}

export function displaySensitivityLabel(value: string): string {
  return SENSITIVITY_DISPLAY[value as SensitivityLabel] ?? value;
}

export function formatBreadthPercent(value: number | null): string {
  if (value === null) return UNAVAILABLE;
  return `${value.toFixed(1)}%`;
}

export function formatBreadthMomentum(value: number | null): string {
  if (value === null) return UNAVAILABLE;
  return `${value.toFixed(1)} pp`;
}

export function formatAdvanceDeclineRatio(value: number | null): string {
  if (value === null) return UNAVAILABLE;
  return value.toFixed(2);
}

export function formatBeta(value: number | null): string {
  if (value === null) return UNAVAILABLE;
  return value.toFixed(4);
}

export function formatCi(lower: number | null, upper: number | null): string {
  if (lower === null || upper === null) return UNAVAILABLE;
  return `[${formatBeta(lower)}, ${formatBeta(upper)}]`;
}

export function formatPValue(value: number | null): string {
  if (value === null) return UNAVAILABLE;
  if (value < 0.001) return "<0.001";
  return value.toFixed(3);
}

export function formatEffect10bp(value: number | null): string {
  if (value === null) return UNAVAILABLE;
  const signed = (value * 100).toFixed(2);
  const prefix = Number(signed) > 0 ? "+" : "";
  return `${prefix}${signed}%`;
}

export function formatGeneratedAt(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
}

export function formatAsOfLong(value: string | undefined): string {
  if (!value) return "Unavailable";
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function formatHeaderDate(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  const datePart = value.includes("T") ? value.slice(0, 10) : value;
  const formatted = formatAsOfLong(datePart);
  return formatted === "Unavailable" ? formatted : formatted.toUpperCase();
}

export function formatRunStatus(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  return value.replaceAll("_", " ").toUpperCase();
}

export function formatEvidenceValue(
  metric: string,
  value: string | number | null,
): string {
  if (value === null) return UNAVAILABLE;
  if (typeof value === "string") {
    if (metric === "trend_regime" || metric.endsWith("sensitivity_label")) {
      return metric === "trend_regime"
        ? displayTrendRegime(value)
        : displaySensitivityLabel(value);
    }
    return value;
  }
  if (metric.startsWith("pct_above_") || metric.includes("pct_above")) {
    return formatBreadthPercent(value);
  }
  if (metric === "breadth_momentum_20d") return formatBreadthMomentum(value);
  if (metric === "advance_decline_ratio") return formatAdvanceDeclineRatio(value);
  if (metric.includes("beta_yield") || metric.includes("ci_95")) {
    return formatBeta(value);
  }
  if (metric.includes("p_value")) return formatPValue(value);
  if (metric.includes("effect_10bp")) return formatEffect10bp(value);
  if (metric.includes("distance_to_sma")) {
    const signed = (value * 100).toFixed(2);
    const prefix = Number(signed) > 0 ? "+" : "";
    return `${prefix}${signed}%`;
  }
  if (Number.isInteger(value)) return String(value);
  return String(value);
}
