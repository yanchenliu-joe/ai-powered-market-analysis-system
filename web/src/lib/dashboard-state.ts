import type { DashboardSnapshot, SnapshotLoadError } from "../types/market";

export type PresentationAlert = {
  level: "critical" | "notice";
  message: string;
};

function parseError(
  errors: SnapshotLoadError[],
  file: string,
): SnapshotLoadError | undefined {
  return errors.find(
    (item) => item.file === file && item.message.startsWith("Could not parse"),
  );
}

export function collectPresentationAlerts(
  snapshot: DashboardSnapshot,
): PresentationAlert[] {
  const alerts: PresentationAlert[] = [];
  const quantParse = parseError(snapshot.errors, "quant_summary.json");
  const marketParse = parseError(snapshot.errors, "market_summary.json");

  if (snapshot.quant === null) {
    alerts.push({
      level: "critical",
      message: quantParse
        ? "The quantitative snapshot is unreadable. Metric cards and charts cannot be shown."
        : "The quantitative snapshot is missing. Metric cards and charts cannot be shown.",
    });
  }
  if (snapshot.market === null) {
    alerts.push({
      level: snapshot.quant === null ? "critical" : "notice",
      message: marketParse
        ? "The interpretation snapshot is unreadable. AI sections cannot be shown."
        : "The interpretation snapshot is missing. AI sections are unavailable.",
    });
  } else if (snapshot.market.status !== "available") {
    alerts.push({
      level: "notice",
      message:
        "AI interpretation was unavailable for this run. Quantitative results remain valid.",
    });
  }
  if (!snapshot.snapshotConsistent) {
    alerts.push({
      level: "critical",
      message:
        "Snapshot identity is inconsistent. Artifacts do not share the same run_id and as-of date.",
    });
  }
  return alerts;
}

export function displayEvidenceSource(source: string): string {
  const labels: Record<string, string> = {
    spy_trend: "SPY Trend",
    sector_rate_sensitivity: "Sector Rate Sensitivity",
    breadth: "Breadth",
  };
  return labels[source] ?? source;
}

export function displayEvidenceMetric(metric: string): string {
  return metric;
}

const PROSE_ENUM_REPLACEMENTS: Array<[string, string]> = [
  ["negative_not_significant", "negative but not statistically significant"],
  ["positive_not_significant", "positive but not statistically significant"],
  ["negative_significant", "negative and statistically significant"],
  ["positive_significant", "positive and statistically significant"],
  ["insufficient_data", "insufficient data"],
];

export function humanizeAiProse(text: string | null | undefined): string {
  if (!text) {
    return "";
  }
  let result = text;
  for (const [token, display] of PROSE_ENUM_REPLACEMENTS) {
    result = result.split(token).join(display);
  }
  return result;
}

export const SURVIVORSHIP_DISPLAY =
  "Historical breadth uses the current S&P 500 constituent universe and is subject to survivorship bias because point-in-time membership is not used.";

function isSurvivorshipLimitation(text: string): boolean {
  const lower = text.toLowerCase();
  return lower.includes("survivorship bias") && lower.includes("s&p 500");
}

export function uniqueLimitations(items: string[]): string[] {
  const displayed: string[] = [];
  let survivorshipShown = false;
  for (const item of items) {
    if (isSurvivorshipLimitation(item)) {
      if (!survivorshipShown) {
        displayed.push(SURVIVORSHIP_DISPLAY);
        survivorshipShown = true;
      }
      continue;
    }
    displayed.push(item);
  }
  return displayed;
}
