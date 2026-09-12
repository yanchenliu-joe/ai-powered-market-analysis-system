"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { RangeControls } from "@/components/RangeControls";
import {
  BREADTH_REFERENCE_PERCENT,
  BREADTH_Y_DOMAIN,
  buildBreadthPlotRows,
  formatBreadthTooltipLines,
  formatBreadthTooltipPercent,
  latestNonNull,
  usableBreadthSeries,
} from "@/lib/chart-data";
import { DEFAULT_CHART_RANGE, filterSeriesByRange, type ChartRange } from "@/lib/range";
import type { BreadthTimeseries } from "@/types/market";

const COLOR_50 = "#1e4a3c";
const COLOR_200 = "#3d6f8a";

function BreadthTooltip({
  active,
  label,
  payload,
}: {
  active?: boolean;
  label?: string;
  payload?: Array<{ dataKey?: string | number; value?: number }>;
}) {
  if (!active || !payload?.length || !label) {
    return null;
  }
  const pct50 = payload.find((item) => item.dataKey === "pct_above_50dma")?.value;
  const pct200 = payload.find((item) => item.dataKey === "pct_above_200dma")?.value;
  const lines = formatBreadthTooltipLines(label, pct50, pct200);
  if (lines.length <= 1) {
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

export function BreadthChart({
  data,
}: {
  data: BreadthTimeseries | null;
}) {
  const [range, setRange] = useState<ChartRange>(DEFAULT_CHART_RANGE);
  const series = usableBreadthSeries(data);
  if (series === null) {
    return (
      <p className="empty-note">
        Historical breadth series not available in this snapshot.
      </p>
    );
  }

  const visible = filterSeriesByRange(series, range);
  const rows = buildBreadthPlotRows(visible);
  const latest50 = latestNonNull(series.map((row) => row.pct_above_50dma));
  const latest200 = latestNonNull(series.map((row) => row.pct_above_200dma));

  return (
    <div>
      <div className="chart-toolbar">
        <p className="caption">
          Share of current S&P 500 constituents above their accepted 50-day and
          200-day moving averages. Range controls only hide already-exported
          dates. As of {data?.as_of_date}.
        </p>
        <RangeControls value={range} onChange={setRange} />
      </div>
      <p className="chart-latest">
        Latest above 50DMA:{" "}
        {latest50 === null ? "Unavailable" : formatBreadthTooltipPercent(latest50)}
        {" · "}
        Latest above 200DMA:{" "}
        {latest200 === null
          ? "Unavailable"
          : formatBreadthTooltipPercent(latest200)}
      </p>
      <div className="chart-frame" role="img" aria-label="Market breadth line chart">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "var(--chart-tick)", fontSize: 12 }} />
            <YAxis
              domain={BREADTH_Y_DOMAIN}
              tickFormatter={(value: number) => `${value}%`}
              tick={{ fill: "var(--chart-tick)", fontSize: 12 }}
              width={48}
            />
            <ReferenceLine
              y={BREADTH_REFERENCE_PERCENT}
              stroke="var(--text-muted)"
              strokeDasharray="4 4"
            />
            <Tooltip content={<BreadthTooltip />} isAnimationActive={false} />
            <Legend />
            <Line
              type="monotone"
              dataKey="pct_above_50dma"
              name="Above 50DMA"
              stroke={COLOR_50}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="pct_above_200dma"
              name="Above 200DMA"
              stroke={COLOR_200}
              strokeWidth={2}
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
