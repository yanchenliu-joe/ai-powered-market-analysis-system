import assert from "node:assert/strict";
import test from "node:test";

import {
  BREADTH_REFERENCE_PERCENT,
  BREADTH_Y_DOMAIN,
  buildBreadthPlotRows,
  buildTrendPlotRows,
  formatBreadthTooltipLines,
  formatTrendTooltipLines,
  toPlotValue,
  usableBreadthSeries,
  usableTrendSeries,
} from "./chart-data.ts";
import { applySnapshotGuards, collectIdentityErrors } from "./snapshot.ts";
import type {
  BreadthTimeseries,
  DashboardSnapshot,
  QuantSummary,
  TrendTimeseries,
} from "../types/market.ts";

test("null breadth values are not converted to zero", () => {
  assert.equal(toPlotValue(null), undefined);
  assert.equal(toPlotValue(0), 0);
  const rows = buildBreadthPlotRows([
    {
      date: "2026-01-02",
      pct_above_50dma: null,
      pct_above_200dma: 58.5,
      advancers: 1,
      decliners: 1,
      advance_decline_ratio: 1,
      net_advances: 0,
      breadth_momentum_20d: null,
    },
  ]);
  assert.equal(rows[0].pct_above_50dma, undefined);
  assert.equal(rows[0].pct_above_200dma, 58.5);
});

test("null SMA values are not converted to zero", () => {
  const rows = buildTrendPlotRows([
    {
      date: "2026-01-02",
      adjusted_close: 765.63,
      sma_20: null,
      sma_50: null,
      sma_200: null,
      trend_regime: "insufficient_data",
    },
  ]);
  assert.equal(rows[0].sma_20, undefined);
  assert.equal(rows[0].sma_50, undefined);
  assert.equal(rows[0].sma_200, undefined);
  assert.equal(rows[0].adjusted_close, 765.63);
});

test("breadth y-domain is 0-100 and has a 50 percent reference", () => {
  assert.deepEqual(BREADTH_Y_DOMAIN, [0, 100]);
  assert.equal(BREADTH_REFERENCE_PERCENT, 50);
});

test("tooltip formatting omits missing values", () => {
  assert.deepEqual(formatBreadthTooltipLines("2026-09-11", 38.1, 58.5), [
    "Date: 2026-09-11",
    "Above 50DMA: 38.1%",
    "Above 200DMA: 58.5%",
  ]);
  assert.deepEqual(
    formatTrendTooltipLines({
      spy: 765.63,
      sma20: 766.95,
      sma50: 758.64,
      sma200: 712.06,
    }),
    [
      "SPY: $765.63",
      "SMA20: $766.95",
      "SMA50: $758.64",
      "SMA200: $712.06",
    ],
  );
  assert.deepEqual(formatTrendTooltipLines({ spy: 765.63 }), ["SPY: $765.63"]);
});

test("missing or invalid series fall back to unused charts", () => {
  assert.equal(usableBreadthSeries(null), null);
  assert.equal(
    usableBreadthSeries({
      schema_version: "1.0.0",
      run_id: "x",
      as_of_date: "2026-09-11",
      series: [],
    } satisfies BreadthTimeseries),
    null,
  );
  assert.equal(usableTrendSeries(null), null);
});

test("snapshot inconsistency is surfaced and series are not mixed", () => {
  const quant = {
    run_metadata: { run_id: "a", as_of_date: "2026-09-11" },
  } as QuantSummary;
  const errors = collectIdentityErrors({
    quant,
    market: { run_id: "a", as_of_date: "2026-09-11" } as never,
    manifest: { run_id: "b", as_of_date: "2026-09-11" } as never,
    breadthSeries: {
      run_id: "a",
      as_of_date: "2026-09-11",
      schema_version: "1.0.0",
      series: [],
    } satisfies TrendTimeseries as unknown as BreadthTimeseries,
    trendSeries: null,
  });
  assert.equal(errors.length, 1);
  const guarded = applySnapshotGuards({
    quant,
    market: { run_id: "a", as_of_date: "2026-09-11" } as never,
    manifest: { run_id: "b", as_of_date: "2026-09-11" } as never,
    breadthSeries: {
      schema_version: "1.0.0",
      run_id: "a",
      as_of_date: "2026-09-11",
      series: [],
    },
    trendSeries: {
      schema_version: "1.0.0",
      run_id: "a",
      as_of_date: "2026-09-11",
      series: [],
    },
    errors: [],
    snapshotConsistent: true,
  } as DashboardSnapshot);
  assert.equal(guarded.snapshotConsistent, false);
  assert.equal(guarded.breadthSeries, null);
  assert.equal(guarded.trendSeries, null);
});
