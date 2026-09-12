import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { displayEvidenceMetric } from "./dashboard-state.ts";
import { formatHeaderDate, formatRunStatus } from "./format.ts";
import { reportIdentity } from "./reports.ts";
import type { DashboardSnapshot, QuantSummary } from "../types/market.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const dashboard = readFileSync(path.join(root, "src/components/Dashboard.tsx"), "utf8");
const header = readFileSync(path.join(root, "src/components/ReportHeader.tsx"), "utf8");
const appendix = readFileSync(
  path.join(root, "src/components/TechnicalAppendix.tsx"),
  "utf8",
);
const reportPage = readFileSync(path.join(root, "src/app/report/page.tsx"), "utf8");
const livePage = readFileSync(path.join(root, "src/app/r/[token]/page.tsx"), "utf8");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const range = readFileSync(path.join(root, "src/lib/range.ts"), "utf8");
const rangeControls = readFileSync(
  path.join(root, "src/components/RangeControls.tsx"),
  "utf8",
);
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const quant = JSON.parse(
  readFileSync(path.join(root, "public/data/quant_summary.json"), "utf8"),
) as QuantSummary;
const market = JSON.parse(
  readFileSync(path.join(root, "public/data/market_summary.json"), "utf8"),
);

const snapshot = {
  quant,
  market,
  manifest: null,
  breadthSeries: null,
  trendSeries: null,
  errors: [],
  snapshotConsistent: true,
} as DashboardSnapshot;

test("report header renders and uses actual metadata", () => {
  assert.match(dashboard, /ReportHeader/);
  assert.match(header, /reportIdentity/);
  assert.match(header, /formatHeaderDate\(identity\.asOfDate\)/);
  assert.match(header, /formatHeaderDate\(identity\.generatedAt\)/);
  assert.match(header, /identity\.runId/);
  assert.match(header, /formatRunStatus\(identity\.status\)/);
  const identity = reportIdentity(snapshot);
  assert.equal(identity.runId, "web-live-snapshot");
  assert.equal(identity.asOfDate, "2026-09-11");
  assert.equal(identity.status, "success");
  assert.equal(formatHeaderDate(identity.asOfDate), "SEP 11, 2026");
  assert.equal(formatRunStatus(identity.status), "SUCCESS");
});

test("sample report is labeled as development snapshot", () => {
  assert.match(reportPage, /sample/);
  assert.match(header, /Sample report · Development snapshot/);
  assert.match(header, /Analysis report/);
});

test("live report is not labeled sample", () => {
  assert.equal(livePage.includes("sample"), false);
  assert.match(livePage, /pdfHref=\{pdfHref\}/);
  assert.doesNotMatch(livePage, /sample/);
});

test("Download PDF and Run New Analysis exist in header", () => {
  assert.match(header, /DownloadPdfButton/);
  assert.match(header, /prominent/);
  assert.match(header, /HeroRunButton/);
  assert.match(header, /U\.S\. Equity Market Analysis/);
});

test("interactive Dashboard sections remain", () => {
  for (const heading of [
    "Overall Market State",
    "Grounded AI Market Brief",
    "Market breadth",
    "SPY trend structure",
    "Sector rate sensitivity",
    "Data quality",
  ]) {
    assert.match(dashboard, new RegExp(heading));
  }
  assert.match(dashboard, /01 \/ Market state/);
  assert.match(dashboard, /07 \/ Technical appendix|TechnicalAppendix/);
});

test("standalone Market Participation KPI section is removed", () => {
  assert.equal(dashboard.includes('title="Market participation"'), false);
  assert.equal(dashboard.includes("metric-grid"), false);
});

test("duplicate long-form ReportView is no longer mounted below Dashboard", () => {
  assert.equal(reportPage.includes("ReportView"), false);
  assert.equal(livePage.includes("ReportView"), false);
  assert.match(dashboard, /TechnicalAppendix/);
});

test("technical appendix disclosures exist", () => {
  assert.match(appendix, /Methodology &amp; limitations/);
  assert.match(appendix, /AI grounding evidence/);
  assert.match(appendix, /Data quality warnings/);
  assert.match(appendix, /Run metadata/);
  assert.match(appendix, /<details>/);
  assert.match(appendix, /uniqueLimitations/);
  assert.match(appendix, /displayEvidenceMetric\(item\.metric\)/);
  assert.match(appendix, /data_quality\.warnings/);
  assert.match(appendix, /identity\.runId/);
});

test("evidence metric identities remain unchanged", () => {
  assert.equal(displayEvidenceMetric("XLF.sensitivity_label"), "XLF.sensitivity_label");
  assert.equal(displayEvidenceMetric("pct_above_50dma"), "pct_above_50dma");
  assert.equal(appendix.includes("humanizeAiProse(item.metric)"), false);
});

test("no access token is rendered as metadata", () => {
  assert.equal(header.includes("access_token"), false);
  assert.equal(appendix.includes("access_token"), false);
  assert.equal(appendix.includes("GITHUB_TOKEN"), false);
  assert.equal(appendix.includes("BLOB_READ_WRITE_TOKEN"), false);
  assert.equal(dashboard.includes("access_token"), false);
});

test("charts and range behavior remain", () => {
  assert.match(dashboard, /BreadthChart/);
  assert.match(dashboard, /TrendChart/);
  assert.match(dashboard, /SectorChart/);
  assert.match(range, /filterSeriesByRange/);
  assert.match(rangeControls, /"1Y"/);
  assert.match(rangeControls, /"3Y"/);
  assert.match(rangeControls, /"5Y"/);
});

test("quant/AI visual distinction remains", () => {
  assert.match(dashboard, /Validated quantitative output/);
  assert.match(dashboard, /Grounded AI interpretation/);
  assert.match(dashboard, /variant="quant"/);
  assert.match(dashboard, /variant="ai"/);
});

test("report sections are editorial not panel cards", () => {
  const section = readFileSync(path.join(root, "src/components/Section.tsx"), "utf8");
  assert.match(section, /home-section report-section/);
  assert.equal(section.includes("panel panel-"), false);
  assert.match(css, /\.page\.page-report[\s\S]*display:\s*block/);
  assert.match(css, /\.chart-toolbar \.range-toggle[\s\S]*width:\s*max-content/);
});

test("homepage remains untouched", () => {
  assert.match(productHome, /AI-Powered Market Analysis/);
  assert.match(productHome, /TrustAccordion/);
  assert.match(homePage, /ProductHome/);
  assert.equal(productHome.includes("ReportHeader"), false);
  assert.equal(productHome.includes("TechnicalAppendix"), false);
});

test("report shell keeps dashboard width and appendix text measure", () => {
  assert.match(css, /\.report-appendix-lede[\s\S]*max-width:\s*68ch/);
  assert.equal(css.includes(".page-report {"), true);
});
