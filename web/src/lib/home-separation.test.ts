import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { NAV_LINKS, REPORT_NAV_LINKS } from "./nav.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const heroRun = readFileSync(path.join(root, "src/components/HeroRunButton.tsx"), "utf8");
const heroPreview = readFileSync(
  path.join(root, "src/components/HeroSystemPreview.tsx"),
  "utf8",
);
const reportPage = readFileSync(path.join(root, "src/app/report/page.tsx"), "utf8");
const dashboard = readFileSync(path.join(root, "src/components/Dashboard.tsx"), "utf8");
const navbar = readFileSync(path.join(root, "src/components/Navbar.tsx"), "utf8");
const dataLoader = readFileSync(path.join(root, "src/lib/data.ts"), "utf8");
const homeTree = `${homePage}\n${productHome}\n${heroPreview}`;

const FORBIDDEN_HOME_COPY = [
  "Overall Market State",
  "Validated Quantitative Output",
  "Grounded AI Market Brief",
  "Sector rate sensitivity",
  "Data quality",
  "Data Quality",
  "View Latest Report",
  "Explore Report History",
  "Latest Validated Report",
];

const FORBIDDEN_HOME_VALUES = ["38.1%", "58.5%", "-30.5 pp", "2.30", "Uptrend"];

const REQUIRED_HOME_COPY = [
  "AI-Powered Market Analysis",
  "Run New Analysis",
  "What the system analyzes",
  "How it works",
  "Built for reproducible market research",
  "Run the analysis pipeline",
];

test("homepage does not import or mount the analytical Dashboard", () => {
  assert.equal(homePage.includes("Dashboard"), false);
  assert.equal(homePage.includes("loadDashboardSnapshot"), false);
  assert.match(homePage, /ProductHome/);
  assert.equal(productHome.includes("from \"@/components/Dashboard\""), false);
  assert.equal(productHome.includes("BreadthChart"), false);
  assert.equal(productHome.includes("TrendChart"), false);
  assert.equal(productHome.includes("SectorChart"), false);
  assert.equal(productHome.includes("quant_summary"), false);
  assert.equal(productHome.includes("market_summary"), false);
});

test("homepage loader is not used for shared report metadata", () => {
  assert.equal(dataLoader.includes("loadHomeSnapshotMetadata"), false);
  assert.match(dataLoader, /export async function loadDashboardSnapshot/);
});

test("homepage does not render analytical section copy", () => {
  for (const phrase of FORBIDDEN_HOME_COPY) {
    assert.equal(homeTree.includes(phrase), false, phrase);
  }
});

test("homepage does not render current analytical values", () => {
  for (const value of FORBIDDEN_HOME_VALUES) {
    assert.equal(homeTree.includes(value), false, value);
  }
});

test("homepage renders required product sections", () => {
  const renderedHome = `${productHome}\n${heroRun}`;
  for (const phrase of REQUIRED_HOME_COPY) {
    assert.match(renderedHome, new RegExp(phrase));
  }
});

test("report page mounts Dashboard and full report", () => {
  assert.match(reportPage, /<Dashboard /);
  assert.equal(reportPage.includes("<ReportView "), false);
  assert.match(reportPage, /<ReportSubnav /);
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
  assert.match(dashboard, /TechnicalAppendix/);
  assert.match(dashboard, /ReportHeader/);
});

test("global nav is product-oriented and report nav is report-only", () => {
  assert.deepEqual(
    NAV_LINKS.map((item) => item.label),
    ["Product", "How It Works", "Methodology"],
  );
  assert.equal(NAV_LINKS.some((item) => item.label === "Reports"), false);
  assert.equal(navbar.includes("Reports"), false);
  assert.deepEqual(
    REPORT_NAV_LINKS.map((item) => item.label),
    ["Overview", "Breadth", "SPY Trend", "Sector Rates", "AI Analysis", "Appendix"],
  );
});
