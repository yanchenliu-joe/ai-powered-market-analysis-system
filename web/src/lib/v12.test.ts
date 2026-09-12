import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { NAV_LINKS, REPORT_NAV_LINKS } from "./nav.ts";
import { DEFAULT_CHART_RANGE, filterSeriesByRange, rangeStartDate } from "./range.ts";
import { PIPELINE_PHASES, snapshotRunStatus } from "./pipeline.ts";
import { authorizeOwner } from "./run-auth.ts";
import { executeRunTrigger } from "./run-trigger.ts";
import { displayTrendRegime } from "./format.ts";
import { SECTOR_ORDER, buildSectorPlotRows } from "./sectors.ts";
import type { QuantSummary } from "../types/market.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");

test("navigation anchors are stable", () => {
  assert.deepEqual(
    NAV_LINKS.map((item) => item.href),
    ["/#product", "/#how-it-works", "/#methodology"],
  );
  assert.deepEqual(
    REPORT_NAV_LINKS.map((item) => item.href),
    [
      "/report#overview",
      "/report#breadth",
      "/report#trend",
      "/report#sector-rates",
      "/report#ai-analysis",
      "/report#appendix",
    ],
  );
});

test("range filtering only slices existing observations and keeps nulls", () => {
  const series = [
    { date: "2021-09-11", value: null as number | null },
    { date: "2024-09-11", value: 12.5 },
    { date: "2025-09-11", value: null },
    { date: "2026-09-11", value: 38.1 },
  ];
  assert.equal(DEFAULT_CHART_RANGE, "5Y");
  assert.equal(rangeStartDate("2026-09-11", "1Y"), "2025-09-11");
  const oneYear = filterSeriesByRange(series, "1Y");
  assert.deepEqual(
    oneYear.map((row) => row.date),
    ["2025-09-11", "2026-09-11"],
  );
  assert.equal(oneYear[0]?.value, null);
  assert.equal(oneYear[1]?.value, 38.1);
});

test("Overall Market State reads accepted fields only", () => {
  const dashboard = readFileSync(
    path.join(root, "src/components/Dashboard.tsx"),
    "utf8",
  );
  assert.match(dashboard, /Overall Market State/);
  assert.match(dashboard, /quant\.trend\.trend_regime/);
  assert.match(dashboard, /pct_above_50dma/);
  assert.equal(dashboard.includes("Bullish Score"), false);
  assert.equal(dashboard.includes("Fear Score"), false);
  assert.equal(displayTrendRegime("uptrend"), "Uptrend");
});

test("AI brief reads existing market_summary fields and evidence count", () => {
  const dashboard = readFileSync(
    path.join(root, "src/components/Dashboard.tsx"),
    "utf8",
  );
  assert.match(dashboard, /Grounded AI Market Brief/);
  assert.match(dashboard, /executive_summary/);
  assert.match(dashboard, /evidenceCount/);
  assert.match(dashboard, /key_confirmed_signals/);
  assert.match(dashboard, /risk_flags/);
});

test("Run Analysis modal exposes pipeline states without fake autoplay", () => {
  const modal = readFileSync(
    path.join(root, "src/components/RunAnalysisModal.tsx"),
    "utf8",
  );
  for (const phase of ["idle", "checking", "queued", "failure", "not_configured"]) {
    assert.equal(PIPELINE_PHASES.includes(phase as never), true);
  }
  assert.match(modal, /\/api\/run-analysis/);
  assert.match(modal, /statusUrl/);
  assert.equal(modal.includes("setTimeout("), false);
  assert.equal(snapshotRunStatus("success"), "Success");
  assert.equal(snapshotRunStatus("partial"), "Partial");
});

test("public trigger does not require an owner secret", async () => {
  const notConfigured = await executeRunTrigger({
    env: {},
  });
  assert.equal(notConfigured.status, 503);
  assert.equal(notConfigured.body.phase, "not_configured");
  assert.equal(authorizeOwner("correct-owner-secret", "correct-owner-secret"), true);
});

test("no client OpenAI or GitHub token dependency", () => {
  const files = [
    "src/components/Dashboard.tsx",
    "src/components/Navbar.tsx",
    "src/components/RunAnalysisModal.tsx",
    "src/components/AppShell.tsx",
    "src/app/page.tsx",
    "src/components/ProductHome.tsx",
  ];
  for (const file of files) {
    const text = readFileSync(path.join(root, file), "utf8");
    assert.equal(text.includes("OPENAI_API_KEY"), false, file);
    assert.equal(text.includes("GITHUB_TOKEN"), false, file);
    assert.equal(text.includes("RUN_ANALYSIS_SECRET"), false, file);
    assert.equal(text.includes("BLOB_READ_WRITE_TOKEN"), false, file);
    assert.equal(text.includes("NEXT_PUBLIC_RUN_ANALYSIS_SECRET"), false, file);
    assert.equal(text.includes("sk-"), false, file);
  }
});

test("theme supports system light and dark", () => {
  const toggle = readFileSync(path.join(root, "src/components/ThemeToggle.tsx"), "utf8");
  assert.match(toggle, /system/);
  assert.match(toggle, /light/);
  assert.match(toggle, /dark/);
  const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
  assert.match(css, /html\.dark/);
});

test("sector chart and snapshot values remain unchanged", () => {
  const quant = JSON.parse(
    readFileSync(path.join(root, "public/data/quant_summary.json"), "utf8"),
  ) as QuantSummary;
  const plot = buildSectorPlotRows(quant.sector_regressions);
  assert.equal(plot.length, 11);
  assert.deepEqual(
    plot.map((row) => row.ticker),
    [...SECTOR_ORDER],
  );
  const xlk = quant.sector_regressions.find((row) => row.ticker === "XLK");
  const plotted = plot.find((row) => row.ticker === "XLK");
  assert.equal(plotted?.beta_yield, xlk?.beta_yield);
});
