import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { NAV_LINKS, REPORT_NAV_LINKS } from "./nav.ts";
import { reportIdentity } from "./reports.ts";
import type { DashboardSnapshot, QuantSummary } from "../types/market.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const dashboard = readFileSync(path.join(root, "src/components/Dashboard.tsx"), "utf8");
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const navbar = readFileSync(path.join(root, "src/components/Navbar.tsx"), "utf8");
const layout = readFileSync(path.join(root, "src/app/layout.tsx"), "utf8");
const dataLoader = readFileSync(path.join(root, "src/lib/data.ts"), "utf8");
const reportPage = readFileSync(path.join(root, "src/app/report/page.tsx"), "utf8");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const quant = JSON.parse(
  readFileSync(path.join(root, "public/data/quant_summary.json"), "utf8"),
) as QuantSummary;
const market = JSON.parse(
  readFileSync(path.join(root, "public/data/market_summary.json"), "utf8"),
);

test("Dashboard no longer renders full AI Analysis section", () => {
  assert.equal(dashboard.includes('title="AI analysis"'), false);
  assert.equal(dashboard.includes("market_participation"), false);
});

test("Dashboard no longer renders full Methodology block", () => {
  assert.equal(dashboard.includes("Methodology & disclaimer"), false);
  assert.equal(dashboard.includes("uniqueLimitations"), false);
});

test("Dashboard keeps AI Executive Summary", () => {
  assert.match(dashboard, /Grounded AI Market Brief/);
  assert.match(dashboard, /executive_summary/);
});

test("homepage has no shared latest-report or history CTAs", () => {
  assert.equal(productHome.includes("View Latest Report"), false);
  assert.equal(productHome.includes("Explore Report History"), false);
  assert.equal(productHome.includes("Latest Validated Report"), false);
  assert.equal(productHome.includes("/reports"), false);
  assert.match(homePage, /ProductHome/);
});

test("/report renders full structured report", () => {
  assert.match(dashboard, /Overall Market State/);
  assert.match(dashboard, /Grounded AI Market Brief/);
  assert.match(dashboard, /TechnicalAppendix/);
  assert.match(reportPage, /<Dashboard /);
  assert.equal(reportPage.includes("<ReportView "), false);
});

test("/reports route is removed", () => {
  assert.equal(existsSync(path.join(root, "src/app/reports/page.tsx")), false);
  assert.equal(existsSync(path.join(root, "src/components/ReportsHistory.tsx")), false);
});

test("run_id and as_of_date match across report identity", () => {
  const snapshot = {
    quant,
    market,
    manifest: null,
    breadthSeries: null,
    trendSeries: null,
    errors: [],
    snapshotConsistent: true,
  } as DashboardSnapshot;
  const identity = reportIdentity(snapshot);
  assert.equal(identity.runId, market.run_id);
  assert.equal(identity.asOfDate, market.as_of_date);
  assert.equal(identity.runId, quant.run_metadata.run_id);
});

test("shared loader is reused by /report only", () => {
  assert.match(reportPage, /loadDashboardSnapshot/);
  assert.match(dataLoader, /export async function loadDashboardSnapshot/);
  assert.equal(dataLoader.includes("loadHomeSnapshotMetadata"), false);
});

test("dark theme semantic tokens exist and are used", () => {
  for (const token of [
    "--bg",
    "--surface",
    "--surface-elevated",
    "--text-primary",
    "--text-secondary",
    "--text-muted",
    "--border",
    "--quant-accent",
    "--ai-accent",
    "--chart-tooltip-bg",
    "--chart-tooltip-text",
  ]) {
    assert.equal(css.includes(token), true, token);
  }
  assert.match(css, /html\.dark/);
  assert.match(css, /color: var\(--text-secondary\)/);
});

test("chart tooltip dark mode has explicit readable colors", () => {
  assert.match(css, /\.chart-tooltip[\s\S]*var\(--chart-tooltip-bg\)/);
  assert.match(css, /\.chart-tooltip[\s\S]*var\(--chart-tooltip-text\)/);
});

test("navbar and theme work on all routes", () => {
  assert.match(layout, /AppShell/);
  assert.match(navbar, /ThemeToggle/);
  assert.match(navbar, /Run Analysis/);
  assert.deepEqual(
    NAV_LINKS.map((item) => item.href),
    ["/#product", "/#how-it-works", "/#methodology"],
  );
  assert.deepEqual(
    REPORT_NAV_LINKS.map((item) => item.label),
    ["Overview", "Breadth", "SPY Trend", "Sector Rates", "AI Analysis", "Appendix"],
  );
});

test("no quantitative or chart data changed", () => {
  assert.equal(quant.breadth.pct_above_50dma, 38.12375249500998);
  assert.equal(quant.run_metadata.run_id, "web-live-snapshot");
});
