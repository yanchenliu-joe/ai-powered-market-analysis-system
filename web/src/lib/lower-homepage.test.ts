import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const trust = readFileSync(path.join(root, "src/components/TrustAccordion.tsx"), "utf8");
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const modal = readFileSync(path.join(root, "src/components/RunAnalysisModal.tsx"), "utf8");
const trigger = readFileSync(path.join(root, "src/lib/run-trigger.ts"), "utf8");
const runButton = readFileSync(path.join(root, "src/components/RunAnalysisButton.tsx"), "utf8");
const homeTree = `${homePage}\n${productHome}\n${trust}`;

test("Trust accordion has all four rows", () => {
  for (const title of ["DETERMINISTIC", "VALIDATED", "GROUNDED", "RESILIENT"]) {
    assert.match(trust, new RegExp(title));
  }
  assert.match(productHome, /TrustAccordion/);
  assert.match(productHome, /05 \/ Trust/);
});

test("Trust rows toggle with one open at a time", () => {
  assert.match(trust, /onClick/);
  assert.match(trust, /current === item\.title \? null : item\.title/);
  assert.match(trust, /useState<string \| null>\(null\)/);
  assert.equal(trust.includes("onMouseEnter"), false);
});

test("Trust aria-expanded and keyboard toggle work", () => {
  assert.match(trust, /type="button"/);
  assert.match(trust, /aria-expanded=\{expanded\}/);
});

test("Trust detail bullets exist", () => {
  for (const item of [
    "The language model does not recompute quantitative metrics",
    "Snapshot identity checks prevent mixed run outputs",
    "AI interpretation may cite only validated evidence paths",
    "Quantitative outputs remain available even if AI interpretation fails",
  ]) {
    assert.match(trust, new RegExp(item));
  }
});

test("Trust reduced motion is supported", () => {
  assert.match(css, /prefers-reduced-motion[\s\S]*\.trust-item-detail\.is-open[\s\S]*animation:\s*none/);
});

test("Workflow renders six numbered steps in order", () => {
  const order = [
    "FETCH MARKET DATA",
    "COMPUTE BREADTH & TREND",
    "RUN SECTOR REGRESSIONS",
    "VALIDATE OUTPUTS",
    "GENERATE GROUNDED AI",
    "PUBLISH REPORT",
  ];
  let cursor = 0;
  for (const step of order) {
    const next = productHome.indexOf(step, cursor);
    assert.ok(next > cursor, step);
    cursor = next;
  }
  assert.match(productHome, /Fetch market data/);
  assert.match(productHome, /Publish a new report/);
});

test("Workflow CTA remains and no fake stages were added", () => {
  assert.match(productHome, /<RunAnalysisButton \/>/);
  assert.match(productHome, /Run the analysis pipeline/);
  assert.equal(productHome.includes("REAL-TIME"), false);
  assert.equal(productHome.includes("Forecast"), false);
});

test("Final CTA has dedicated light and dark surfaces", () => {
  assert.match(css, /--home-cta-field:\s*#eaf3f7/);
  assert.match(css, /html\.dark[\s\S]*--home-cta-field:\s*#1e2a2f/);
  assert.match(css, /\.home-final-cta[\s\S]*background:\s*var\(--home-cta-field\)/);
  assert.match(css, /html\.dark \.home-final-cta/);
  assert.match(productHome, /home-final-cta/);
});

test("Start Analysis still uses existing handler", () => {
  assert.match(productHome, /label="START ANALYSIS"/);
  assert.match(runButton, /open-run-analysis/);
  assert.doesNotMatch(productHome, /home-final-cta[\s\S]{0,80}onClick/);
});

test("homepage still contains no current market result data", () => {
  for (const value of ["38.1%", "58.5%", "-30.5 pp", "2.30", "Uptrend"]) {
    assert.equal(homeTree.includes(value), false, value);
  }
});

test("backend/run behavior is unchanged", () => {
  assert.match(modal, /fetch\("\/api\/run-analysis"/);
  assert.match(trigger, /executeRunTrigger/);
  assert.equal(existsSync(path.join(root, "src/app/r/[token]/page.tsx")), true);
});
