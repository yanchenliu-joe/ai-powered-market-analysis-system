import type {
  BreadthTimeseries,
  BreadthTimeseriesPoint,
  TrendTimeseries,
  TrendTimeseriesPoint,
} from "@/types/market";

export const BREADTH_Y_DOMAIN: [number, number] = [0, 100];
export const BREADTH_REFERENCE_PERCENT = 50;

export function isChartNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function isNullableChartNumber(value: unknown): value is number | null {
  return value === null || isChartNumber(value);
}

export function toPlotValue(value: number | null): number | undefined {
  if (value === null) {
    return undefined;
  }
  return value;
}

export function formatBreadthTooltipPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatTrendTooltipPrice(value: number): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function latestNonNull(
  series: Array<number | null | undefined>,
): number | null {
  for (let index = series.length - 1; index >= 0; index -= 1) {
    const value = series[index];
    if (isChartNumber(value)) {
      return value;
    }
  }
  return null;
}

function hasDate(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

export function isValidBreadthPoint(
  point: unknown,
): point is BreadthTimeseriesPoint {
  if (point === null || typeof point !== "object") {
    return false;
  }
  const row = point as BreadthTimeseriesPoint;
  return (
    hasDate(row.date) &&
    isNullableChartNumber(row.pct_above_50dma) &&
    isNullableChartNumber(row.pct_above_200dma)
  );
}

export function isValidTrendPoint(point: unknown): point is TrendTimeseriesPoint {
  if (point === null || typeof point !== "object") {
    return false;
  }
  const row = point as TrendTimeseriesPoint;
  return (
    hasDate(row.date) &&
    isChartNumber(row.adjusted_close) &&
    isNullableChartNumber(row.sma_20) &&
    isNullableChartNumber(row.sma_50) &&
    isNullableChartNumber(row.sma_200)
  );
}

export function usableBreadthSeries(
  data: BreadthTimeseries | null,
): BreadthTimeseriesPoint[] | null {
  if (data === null || !Array.isArray(data.series) || data.series.length === 0) {
    return null;
  }
  if (!data.series.every(isValidBreadthPoint)) {
    return null;
  }
  return data.series;
}

export function usableTrendSeries(
  data: TrendTimeseries | null,
): TrendTimeseriesPoint[] | null {
  if (data === null || !Array.isArray(data.series) || data.series.length === 0) {
    return null;
  }
  if (!data.series.every(isValidTrendPoint)) {
    return null;
  }
  return data.series;
}

export function buildBreadthPlotRows(series: BreadthTimeseriesPoint[]) {
  return series.map((row) => ({
    date: row.date,
    pct_above_50dma: toPlotValue(row.pct_above_50dma),
    pct_above_200dma: toPlotValue(row.pct_above_200dma),
  }));
}

export function buildTrendPlotRows(series: TrendTimeseriesPoint[]) {
  return series.map((row) => ({
    date: row.date,
    adjusted_close: row.adjusted_close,
    sma_20: toPlotValue(row.sma_20),
    sma_50: toPlotValue(row.sma_50),
    sma_200: toPlotValue(row.sma_200),
  }));
}

export function formatBreadthTooltipLines(
  date: string,
  pct50: number | undefined,
  pct200: number | undefined,
): string[] {
  const lines = [`Date: ${date}`];
  if (isChartNumber(pct50)) {
    lines.push(`Above 50DMA: ${formatBreadthTooltipPercent(pct50)}`);
  }
  if (isChartNumber(pct200)) {
    lines.push(`Above 200DMA: ${formatBreadthTooltipPercent(pct200)}`);
  }
  return lines;
}

export function formatTrendTooltipLines(values: {
  spy?: number;
  sma20?: number;
  sma50?: number;
  sma200?: number;
}): string[] {
  const lines: string[] = [];
  if (isChartNumber(values.spy)) {
    lines.push(`SPY: ${formatTrendTooltipPrice(values.spy)}`);
  }
  if (isChartNumber(values.sma20)) {
    lines.push(`SMA20: ${formatTrendTooltipPrice(values.sma20)}`);
  }
  if (isChartNumber(values.sma50)) {
    lines.push(`SMA50: ${formatTrendTooltipPrice(values.sma50)}`);
  }
  if (isChartNumber(values.sma200)) {
    lines.push(`SMA200: ${formatTrendTooltipPrice(values.sma200)}`);
  }
  return lines;
}
