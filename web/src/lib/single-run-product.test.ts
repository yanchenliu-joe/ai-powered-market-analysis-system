import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { NAV_LINKS } from "./nav.ts";
import { MARKET_REPORT_PDF_FILENAME, MARKET_REPORT_PDF_HREF } from "./pdf.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const reportView = readFileSync(path.join(root, "src/components/ReportView.tsx"), "utf8");
const dashboard = readFileSync(path.join(root, "src/components/Dashboard.tsx"), "utf8");
const modal = readFileSync(path.join(root, "src/components/RunAnalysisModal.tsx"), "utf8");
const download = readFileSync(
  path.join(root, "src/components/DownloadPdfButton.tsx"),
  "utf8",
);
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const range = readFileSync(path.join(root, "src/lib/range.ts"), "utf8");
const footer = readFileSync(path.join(root, "src/components/SiteFooter.tsx"), "utf8");
const frontendTree = [
  productHome,
  homePage,
  reportView,
  dashboard,
  modal,
  download,
  footer,
].join("\n");

test("homepage has no View Latest Report", () => {
  assert.equal(productHome.includes("View Latest Report"), false);
  assert.equal(homePage.includes("View Latest Report"), false);
});

test("homepage has no Explore Report History", () => {
  assert.equal(productHome.includes("Explore Report History"), false);
});

test("homepage has no shared latest-report metadata card", () => {
  assert.equal(productHome.includes("Latest Validated Report"), false);
  assert.equal(productHome.includes("latest-report-card"), false);
});

test("global navbar has no Reports link", () => {
  assert.equal(
    NAV_LINKS.some((item) => item.label === "Reports"),
    false,
  );
  assert.equal(
    NAV_LINKS.some((item) => item.href.includes("/reports")),
    false,
  );
});

test("/reports no longer exists", () => {
  assert.equal(existsSync(path.join(root, "src/app/reports/page.tsx")), false);
});

test("/report still renders the full analysis", () => {
  assert.match(dashboard, /ReportHeader/);
  assert.match(dashboard, /Overall Market State/);
  assert.match(dashboard, /TechnicalAppendix/);
});

test("/report has Download PDF action", () => {
  assert.match(dashboard, /ReportHeader/);
  assert.match(download, /Download PDF/);
  assert.match(download, /MARKET_REPORT_PDF_HREF/);
});

test("/report does not link to history", () => {
  assert.equal(reportView.includes('href="/reports"'), false);
  assert.equal(dashboard.includes('href="/reports"'), false);
  assert.equal(footer.includes('href="/reports"'), false);
});

test("Run Analysis remains available", () => {
  assert.match(productHome, /HeroRunButton/);
  assert.match(productHome, /RunAnalysisButton/);
  assert.match(dashboard, /ReportHeader/);
  assert.match(modal, /\/api\/run-analysis/);
});

test("no quantitative semantics changed", () => {
  const quant = JSON.parse(
    readFileSync(path.join(root, "public/data/quant_summary.json"), "utf8"),
  );
  assert.equal(quant.breadth.pct_above_50dma, 38.12375249500998);
  assert.equal(quant.run_metadata.run_id, "web-live-snapshot");
});

test("existing chart and range behavior remains", () => {
  assert.match(range, /filterSeriesByRange/);
  assert.match(dashboard, /BreadthChart/);
  assert.match(dashboard, /TrendChart/);
  assert.match(dashboard, /SectorChart/);
});

test("dark mode remains", () => {
  assert.match(css, /html\.dark/);
  assert.match(css, /--text-primary/);
});

test("PDF button references a valid artifact path", () => {
  assert.equal(MARKET_REPORT_PDF_HREF, "/data/market_report.pdf");
  assert.equal(MARKET_REPORT_PDF_FILENAME, "market_report.pdf");
  assert.equal(
    existsSync(path.join(root, "public/data/market_report.pdf")),
    true,
  );
});

test("no login or database dependency added", () => {
  for (const needle of ["prisma", "mongoose", "next-auth", "clerk", "supabase"]) {
    assert.equal(frontendTree.toLowerCase().includes(needle), false, needle);
  }
});
