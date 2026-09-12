import { isChartNumber } from "./chart-data.ts";
import {
  displaySensitivityLabel,
  formatBeta,
  formatCi,
  formatEffect10bp,
  formatPValue,
} from "./format.ts";
import type {
  SectorRegressionSummary,
  SensitivityLabel,
} from "../types/market.ts";

export const SECTOR_ORDER = [
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
] as const;

export const SECTOR_NAMES: Record<(typeof SECTOR_ORDER)[number], string> = {
  XLC: "Communication Services",
  XLY: "Consumer Discretionary",
  XLP: "Consumer Staples",
  XLE: "Energy",
  XLF: "Financials",
  XLV: "Health Care",
  XLI: "Industrials",
  XLK: "Technology",
  XLB: "Materials",
  XLRE: "Real Estate",
  XLU: "Utilities",
};

export const SECTOR_COMPACT_NAMES: Record<(typeof SECTOR_ORDER)[number], string> =
  {
    XLC: "Comm. Services",
    XLY: "Cons. Discretionary",
    XLP: "Cons. Staples",
    XLE: "Energy",
    XLF: "Financials",
    XLV: "Health Care",
    XLI: "Industrials",
    XLK: "Technology",
    XLB: "Materials",
    XLRE: "Real Estate",
    XLU: "Utilities",
  };

export const ZERO_REFERENCE = 0;

export type SignificanceGroup =
  | "significant"
  | "not_significant"
  | "insufficient";

export interface SectorPlotRow {
  ticker: string;
  label: string;
  compactLabel: string;
  beta_yield: number | undefined;
  ci_95_lower: number | null;
  ci_95_upper: number | null;
  ciError: [number, number] | undefined;
  significanceGroup: SignificanceGroup;
  sensitivity_label: SensitivityLabel;
  n_obs: number;
  p_value: number | null;
  effect_10bp: number | null;
}

export function displaySectorName(ticker: string): string {
  const name = SECTOR_NAMES[ticker as (typeof SECTOR_ORDER)[number]];
  return name ? `${ticker} — ${name}` : ticker;
}

export function displaySectorCompactName(ticker: string): string {
  const name = SECTOR_COMPACT_NAMES[ticker as (typeof SECTOR_ORDER)[number]];
  return name ? `${ticker} — ${name}` : ticker;
}

export function significanceGroupFromLabel(
  label: SensitivityLabel,
): SignificanceGroup {
  if (label === "positive_significant" || label === "negative_significant") {
    return "significant";
  }
  if (
    label === "positive_not_significant" ||
    label === "negative_not_significant"
  ) {
    return "not_significant";
  }
  return "insufficient";
}

export function orderSectorRegressions(
  rows: SectorRegressionSummary[],
): SectorRegressionSummary[] {
  const rank = new Map(SECTOR_ORDER.map((ticker, index) => [ticker, index]));
  return [...rows].sort((left, right) => {
    const leftRank = rank.get(left.ticker as (typeof SECTOR_ORDER)[number]);
    const rightRank = rank.get(right.ticker as (typeof SECTOR_ORDER)[number]);
    return (leftRank ?? Number.MAX_SAFE_INTEGER) - (rightRank ?? Number.MAX_SAFE_INTEGER);
  });
}

export function toSectorPlotRow(row: SectorRegressionSummary): SectorPlotRow {
  const group = significanceGroupFromLabel(row.sensitivity_label);
  const beta = row.beta_yield;
  const lower = row.ci_95_lower;
  const upper = row.ci_95_upper;
  const plottable =
    group !== "insufficient" &&
    isChartNumber(beta) &&
    isChartNumber(lower) &&
    isChartNumber(upper);
  return {
    ticker: row.ticker,
    label: displaySectorName(row.ticker),
    compactLabel: displaySectorCompactName(row.ticker),
    beta_yield: plottable ? beta : undefined,
    ci_95_lower: row.ci_95_lower,
    ci_95_upper: row.ci_95_upper,
    ciError: plottable ? [beta - lower, upper - beta] : undefined,
    significanceGroup: group,
    sensitivity_label: row.sensitivity_label,
    n_obs: row.n_obs,
    p_value: row.p_value,
    effect_10bp: row.effect_10bp,
  };
}

export function buildSectorPlotRows(
  rows: SectorRegressionSummary[],
): SectorPlotRow[] {
  return orderSectorRegressions(rows).map(toSectorPlotRow);
}

export function formatSectorTooltipLines(row: SectorPlotRow): string[] {
  if (row.significanceGroup === "insufficient") {
    return [displaySectorName(row.ticker), "Significance: Insufficient Data"];
  }
  return [
    displaySectorName(row.ticker),
    `Beta: ${formatBeta(row.beta_yield ?? null)}`,
    `95% CI: ${formatCi(row.ci_95_lower, row.ci_95_upper)}`,
    `p-value: ${formatPValue(row.p_value)}`,
    `+10bp effect: ${formatEffect10bp(row.effect_10bp)}`,
    `Significance: ${displaySensitivityLabel(row.sensitivity_label)}`,
    `Observations: ${row.n_obs}`,
  ];
}
