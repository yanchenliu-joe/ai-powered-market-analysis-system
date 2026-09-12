"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { RangeControls } from "@/components/RangeControls";
import {
  buildTrendPlotRows,
  formatTrendTooltipLines,
  formatTrendTooltipPrice,
  latestNonNull,
  usableTrendSeries,
} from "@/lib/chart-data";
import { displayTrendRegime } from "@/lib/format";
import { DEFAULT_CHART_RANGE, filterSeriesByRange, type ChartRange } from "@/lib/range";
import type { TrendRegime, TrendTimeseries } from "@/types/market";

const COLOR_SPY = "var(--text-primary)";
const COLOR_SMA20 = "#6a4e24";
const COLOR_SMA50 = "#3d6f8a";
const COLOR_SMA200 = "#8a6d4a";

function TrendTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string | number; value?: number }>;
}) {
  if (!active || !payload?.length) {
    return null;
  }
  const valueOf = (key: string) =>
    payload.find((item) => item.dataKey === key)?.value;
  const lines = formatTrendTooltipLines({
    spy: valueOf("adjusted_close"),
    sma20: valueOf("sma_20"),
    sma50: valueOf("sma_50"),
    sma200: valueOf("sma_200"),
  });
  if (lines.length === 0) {
    return null;
  }
  return (
    <div className="chart-tooltip">
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  );
}

export function TrendChart({
  data,
  trendRegime,
}: {
  data: TrendTimeseries | null;
  trendRegime: TrendRegime | null;
}) {
  const [range, setRange] = useState<ChartRange>(DEFAULT_CHART_RANGE);
  const series = usableTrendSeries(data);
  if (series === null) {
    return (
      <p className="empty-note">
        Historical trend series not available in this snapshot.
      </p>
    );
  }

  const visible = filterSeriesByRange(series, range);
  const rows = buildTrendPlotRows(visible);
  const latestSpy = latestNonNull(series.map((row) => row.adjusted_close));

  return (
    <div>
      <div className="chart-toolbar">
        <p className="caption">
          SPY adjusted close with accepted SMA20, SMA50, and SMA200 values from
          the Python snapshot. Range filtering does not recompute averages. As
          of {data?.as_of_date}.
        </p>
        <RangeControls value={range} onChange={setRange} />
      </div>
      <p className="chart-latest">
        Current trend regime:{" "}
        {trendRegime ? displayTrendRegime(trendRegime) : "Unavailable"}
        {latestSpy === null
          ? ""
          : ` · Latest SPY: ${formatTrendTooltipPrice(latestSpy)}`}
      </p>
      <div className="chart-frame" role="img" aria-label="SPY trend structure chart">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={rows} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "var(--chart-tick)", fontSize: 12 }} />
            <YAxis
              tickFormatter={(value: number) => formatTrendTooltipPrice(value)}
              tick={{ fill: "var(--chart-tick)", fontSize: 12 }}
              width={72}
            />
            <Tooltip content={<TrendTooltip />} isAnimationActive={false} />
            <Legend />
            <Line
              type="monotone"
              dataKey="adjusted_close"
              name="SPY"
              stroke={COLOR_SPY}
              strokeWidth={2.25}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="sma_20"
              name="SMA20"
              stroke={COLOR_SMA20}
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="sma_50"
              name="SMA50"
              stroke={COLOR_SMA50}
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="sma_200"
              name="SMA200"
              stroke={COLOR_SMA200}
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
