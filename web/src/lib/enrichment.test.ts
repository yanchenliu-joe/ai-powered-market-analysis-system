import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const heroPreview = readFileSync(
  path.join(root, "src/components/HeroSystemPreview.tsx"),
  "utf8",
);
const howItWorks = readFileSync(
  path.join(root, "src/components/HowItWorksPipeline.tsx"),
  "utf8",
);
const modal = readFileSync(path.join(root, "src/components/RunAnalysisModal.tsx"), "utf8");
const navbar = readFileSync(path.join(root, "src/components/Navbar.tsx"), "utf8");
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const trigger = readFileSync(path.join(root, "src/lib/run-trigger.ts"), "utf8");
const homeTree = `${homePage}\n${productHome}\n${heroPreview}\n${howItWorks}`;

const FORBIDDEN_VALUES = ["38.1%", "58.5%", "-30.5 pp", "2.30", "Uptrend"];

test("homepage still contains no analytical results", () => {
  for (const value of FORBIDDEN_VALUES) {
    assert.equal(homeTree.includes(value), false, value);
  }
  assert.equal(homeTree.includes("Overall Market State"), false);
});

test("hero Analysis Engine renders all stages", () => {
  assert.match(heroPreview, /Analysis Engine/);
  for (const stage of [
    "Market Data",
    "Quantitative Engine",
    "Validation Layer",
    "Grounded AI",
    "Research Report",
  ]) {
    assert.match(heroPreview, new RegExp(stage));
  }
});

test("stage interaction changes explanatory UI only", () => {
  assert.match(heroPreview, /hero-preview-detail-list/);
  assert.equal(heroPreview.includes("onFocus"), false);
  assert.equal(heroPreview.includes("onClick"), false);
  assert.equal(heroPreview.includes('className="hero-preview-detail"'), false);
});

test("no API/fetch is triggered by hero interaction", () => {
  assert.equal(heroPreview.includes("fetch("), false);
  assert.equal(heroPreview.includes("/api/"), false);
  assert.equal(howItWorks.includes("fetch("), false);
});

test("four capability cards render", () => {
  for (const title of [
    "Market Breadth",
    "SPY Trend Structure",
    "Sector Rate Sensitivity",
    "Grounded AI Interpretation",
  ]) {
    assert.match(productHome, new RegExp(title));
  }
});

test("capability technical tags render", () => {
  for (const tag of [
    "50DMA · 200DMA · A/D",
    "SMA20 · SMA50 · SMA200",
    "OLS · HC3 · DGS10",
    "Structured Output · Evidence Grounding",
  ]) {
    assert.match(productHome, new RegExp(tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("How It Works stages remain", () => {
  assert.match(productHome, /HowItWorksPipeline/);
  for (const phase of ["Data", "Quant Analytics", "Validation", "AI Research"]) {
    assert.match(howItWorks, new RegExp(phase));
  }
});

test("hover/focus interaction has accessible equivalent", () => {
  assert.equal(heroPreview.includes("<button"), false);
  assert.match(howItWorks, /type="button"/);
  assert.match(howItWorks, /aria-expanded/);
  assert.match(productHome, /tabIndex=\{0\}/);
});

test("Run Analysis modal functionality unchanged", () => {
  assert.match(modal, /fetch\("\/api\/run-analysis"/);
  assert.match(modal, /body\.phase/);
  assert.match(modal, /statusUrl/);
  assert.equal(modal.includes("setTimeout("), false);
});

test("no owner password returns", () => {
  assert.equal(modal.includes("password"), false);
  assert.equal(navbar.includes("password"), false);
});

test("light theme semantic accent tokens exist", () => {
  assert.match(css, /--accent-quant:/);
  assert.match(css, /--accent-data:/);
  assert.match(css, /--accent-ai:/);
  assert.match(css, /--accent-validation:/);
  assert.match(css, /:root[\s\S]*--nb-blue:/);
});

test("dark theme semantic accent tokens exist", () => {
  assert.match(css, /html\.dark[\s\S]*--accent-data:/);
  assert.match(css, /html\.dark[\s\S]*--accent-ai:/);
  assert.match(css, /html\.dark[\s\S]*--accent-validation:/);
  assert.match(css, /html\.dark[\s\S]*--accent-quant:/);
});

test("prefers-reduced-motion is respected", () => {
  assert.match(css, /prefers-reduced-motion/);
});

test("report routes remain buildable", () => {
  assert.equal(existsSync(path.join(root, "src/app/report/page.tsx")), true);
  assert.equal(existsSync(path.join(root, "src/app/r/[token]/page.tsx")), true);
});

test("no backend/API contract changed", () => {
  assert.match(trigger, /executeRunTrigger/);
  assert.equal(modal.includes("payload.secret"), false);
  assert.equal(productHome.includes("OPENAI_API_KEY"), false);
});
