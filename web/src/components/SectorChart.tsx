"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ErrorBar,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  ZERO_REFERENCE,
  buildSectorPlotRows,
  displaySectorCompactName,
  displaySectorName,
  formatSectorTooltipLines,
  type SectorPlotRow,
} from "@/lib/sectors";
import { displaySensitivityLabel } from "@/lib/format";
import type { SectorRegressionSummary } from "@/types/market";

const COLOR_SIGNIFICANT = "#1e4a3c";
const COLOR_NOT_SIGNIFICANT = "#8a8578";
const COLOR_INSUFFICIENT = "#d4cfc2";

function fillFor(group: SectorPlotRow["significanceGroup"]): string {
  if (group === "significant") return COLOR_SIGNIFICANT;
  if (group === "not_significant") return COLOR_NOT_SIGNIFICANT;
  return COLOR_INSUFFICIENT;
}

function SectorTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: SectorPlotRow }>;
}) {
  if (!active || !payload?.[0]?.payload) {
    return null;
  }
  const lines = formatSectorTooltipLines(payload[0].payload);
  return (
    <div className="chart-tooltip">
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  );
}

export function SectorChart({
  rows,
}: {
  rows: SectorRegressionSummary[];
}) {
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 640px)");
    const sync = () => setCompact(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  const plotRows = buildSectorPlotRows(rows);

  return (
    <div>
      <p className="caption">
        Beta represents associated sector return per +1 percentage-point daily
        change in the 10-year Treasury yield. Association does not imply
        causation.
      </p>
      <p className="chart-latest">
        Significance uses the accepted snapshot label only: Significant, Not
        Significant, or Insufficient Data. This is statistical exposure, not a
        trading recommendation.
      </p>
      <ul className="legend-inline" aria-label="Significance categories">
        <li>
          <span className="swatch swatch-quant" />
          Significant
        </li>
        <li>
          <span className="swatch swatch-muted" />
          Not Significant
        </li>
        <li>
          <span className="swatch swatch-insufficient" />
          Insufficient Data
        </li>
      </ul>
      <div
        className="chart-frame chart-frame-sector"
        role="img"
        aria-label="Sector Treasury-yield sensitivity chart with 95 percent confidence intervals"
      >
        <ResponsiveContainer width="100%" height={440}>
          <BarChart
            layout="vertical"
            data={plotRows}
            margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
          >
            <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fill: "var(--chart-tick)", fontSize: 12 }}
              tickFormatter={(value: number) => value.toFixed(2)}
            />
            <YAxis
              type="category"
              dataKey={compact ? "compactLabel" : "label"}
              width={compact ? 118 : 196}
              tick={{ fill: "var(--text-primary)", fontSize: 12 }}
            />
            <ReferenceLine
              x={ZERO_REFERENCE}
              stroke="var(--text-secondary)"
              strokeWidth={1.25}
            />
            <Tooltip content={<SectorTooltip />} isAnimationActive={false} />
            <Bar
              dataKey="beta_yield"
              name="Beta"
              maxBarSize={16}
              isAnimationActive={false}
            >
              {plotRows.map((row) => (
                <Cell
                  key={row.ticker}
                  fill={fillFor(row.significanceGroup)}
                  stroke={
                    row.significanceGroup === "insufficient"
                      ? "#8a8578"
                      : undefined
                  }
                  strokeDasharray={
                    row.significanceGroup === "insufficient" ? "3 3" : undefined
                  }
                />
              ))}
              <ErrorBar
                dataKey="ciError"
                direction="x"
                stroke="var(--text-secondary)"
                width={6}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="sr-only">
        {plotRows.map((row) => (
          <li key={row.ticker}>
            {displaySectorName(row.ticker)}.{" "}
            {row.beta_yield === undefined
              ? "Insufficient Data"
              : `Beta ${row.beta_yield}. ${displaySensitivityLabel(row.sensitivity_label)}.`}
            {compact ? ` Compact label ${displaySectorCompactName(row.ticker)}.` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
