import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  collectPresentationAlerts,
  displayEvidenceSource,
} from "./dashboard-state.ts";
import { applySnapshotGuards } from "./snapshot.ts";
import type { DashboardSnapshot, MarketInterpretation, QuantSummary } from "../types/market.ts";

const emptySnapshot = {
  quant: null,
  market: null,
  manifest: null,
  breadthSeries: null,
  trendSeries: null,
  errors: [],
  snapshotConsistent: true,
} as DashboardSnapshot;

test("critical quant missing error state", () => {
  const alerts = collectPresentationAlerts(emptySnapshot);
  assert.equal(
    alerts.some(
      (item) =>
        item.level === "critical" &&
        item.message.includes("quantitative snapshot is missing"),
    ),
    true,
  );
});

test("missing market_summary is a partial notice when quant exists", () => {
  const alerts = collectPresentationAlerts({
    ...emptySnapshot,
    quant: { run_metadata: { run_id: "a", as_of_date: "2026-09-11" } } as QuantSummary,
  });
  assert.equal(
    alerts.some(
      (item) =>
        item.level === "notice" &&
        item.message.includes("interpretation snapshot is missing"),
    ),
    true,
  );
  assert.equal(
    alerts.some((item) => item.message.includes("quantitative snapshot is missing")),
    false,
  );
});

test("unavailable interpretation state", () => {
  const alerts = collectPresentationAlerts({
    ...emptySnapshot,
    quant: { run_metadata: { run_id: "a", as_of_date: "2026-09-11" } } as QuantSummary,
    market: {
      run_id: "a",
      as_of_date: "2026-09-11",
      status: "unavailable",
    } as MarketInterpretation,
  });
  assert.equal(
    alerts.some((item) => item.message.includes("unavailable for this run")),
    true,
  );
});

test("manifest mismatch error behavior", () => {
  const guarded = applySnapshotGuards({
    ...emptySnapshot,
    quant: { run_metadata: { run_id: "a", as_of_date: "2026-09-11" } } as QuantSummary,
    market: {
      run_id: "a",
      as_of_date: "2026-09-11",
      status: "available",
    } as MarketInterpretation,
    manifest: { run_id: "other", as_of_date: "2026-09-11" } as never,
    snapshotConsistent: true,
  });
  const alerts = collectPresentationAlerts(guarded);
  assert.equal(guarded.snapshotConsistent, false);
  assert.equal(
    alerts.some(
      (item) =>
        item.level === "critical" && item.message.includes("inconsistent"),
    ),
    true,
  );
});

test("evidence source labels are humanized without changing metric identity", () => {
  assert.equal(displayEvidenceSource("spy_trend"), "SPY Trend");
  assert.equal(
    displayEvidenceSource("sector_rate_sensitivity"),
    "Sector Rate Sensitivity",
  );
  assert.equal(displayEvidenceSource("breadth"), "Breadth");
});

test("no OpenAI or external API dependency in the web layer", () => {
  const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
  const files = [
    "lib/data.ts",
    "lib/sectors.ts",
    "lib/dashboard-state.ts",
    "lib/chart-data.ts",
    "components/Dashboard.tsx",
    "app/page.tsx",
    "components/ProductHome.tsx",
  ];
  for (const file of files) {
    const text = readFileSync(path.join(root, file), "utf8");
    assert.equal(text.includes("OPENAI_API_KEY"), false, file);
    assert.equal(text.includes("NEXT_PUBLIC"), false, file);
    assert.equal(text.includes("api.openai.com"), false, file);
  }
});

test("layout uses a constrained page width to avoid structural overflow", () => {
  const css = readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)), "../app/globals.css"),
    "utf8",
  );
  assert.equal(css.includes("max-width: 100%"), true);
  assert.equal(css.includes("overflow-x: auto"), true);
});
