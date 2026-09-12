export type ChartRange = "1Y" | "3Y" | "5Y";

export const DEFAULT_CHART_RANGE: ChartRange = "5Y";

const RANGE_YEARS: Record<ChartRange, number> = {
  "1Y": 1,
  "3Y": 3,
  "5Y": 5,
};

export function addCalendarYears(isoDate: string, years: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const shifted = new Date(Date.UTC(year + years, month - 1, day));
  return shifted.toISOString().slice(0, 10);
}

export function rangeStartDate(latestDate: string, range: ChartRange): string {
  return addCalendarYears(latestDate, -RANGE_YEARS[range]);
}

export function filterSeriesByRange<T extends { date: string }>(
  series: T[],
  range: ChartRange,
): T[] {
  if (series.length === 0) {
    return series;
  }
  const latest = series[series.length - 1]?.date;
  if (!latest) {
    return series;
  }
  const start = rangeStartDate(latest, range);
  return series.filter((row) => row.date >= start);
}
