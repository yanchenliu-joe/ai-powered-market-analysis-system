import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const howItWorks = readFileSync(
  path.join(root, "src/components/HowItWorksPipeline.tsx"),
  "utf8",
);
const heroPreview = readFileSync(
  path.join(root, "src/components/HeroSystemPreview.tsx"),
  "utf8",
);
const capabilityIcon = readFileSync(
  path.join(root, "src/components/HomeCapabilityIcon.tsx"),
  "utf8",
);
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const homeTree = `${homePage}\n${productHome}\n${heroPreview}\n${capabilityIcon}\n${howItWorks}`;

const FORBIDDEN_VALUES = ["38.1%", "58.5%", "-30.5 pp", "2.30", "Uptrend"];
const PIPELINE_CONCEPTS = [
  "Market Data",
  "Data Validation",
  "Breadth & Trend",
  "HC3 Sector Regressions",
  "Validated QuantSummary",
  "Grounded AI Interpretation",
  "Research Report",
];

test("hero system preview renders no current analytical values", () => {
  assert.match(productHome, /HeroSystemPreview/);
  assert.match(heroPreview, /Analysis Engine/);
  assert.match(heroPreview, /System flow/);
  assert.match(heroPreview, /Market Data/);
  assert.match(heroPreview, /Quant Engine/);
  assert.match(heroPreview, /Validated Signals/);
  assert.match(heroPreview, /Grounded AI Report/);
  assert.match(heroPreview, /Quantitative Engine/);
  assert.match(heroPreview, /Research Report/);
  for (const value of FORBIDDEN_VALUES) {
    assert.equal(heroPreview.includes(value), false, value);
  }
});

test("four capability cards remain present", () => {
  for (const title of [
    "Market Breadth",
    "SPY Trend Structure",
    "Sector Rate Sensitivity",
    "Grounded AI Interpretation",
  ]) {
    assert.match(productHome, new RegExp(title));
  }
  assert.match(productHome, /HomeCapabilityIcon/);
});

test("How It Works renders four grouped phases", () => {
  assert.match(productHome, /HowItWorksPipeline/);
  assert.match(howItWorks, /pipeline-phases/);
  for (const phase of ["Data", "Quant Analytics", "Validation", "AI Research", "REPORT"]) {
    assert.match(howItWorks, new RegExp(phase));
  }
  assert.match(howItWorks, /"01"/);
  assert.match(howItWorks, /"05"/);
});

test("all accepted underlying pipeline concepts are still represented", () => {
  for (const concept of PIPELINE_CONCEPTS) {
    assert.match(howItWorks, new RegExp(concept.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("homepage no longer advertises a shared latest report", () => {
  assert.equal(productHome.includes("Latest Validated Report"), false);
  assert.equal(productHome.includes("Open Report"), false);
  assert.equal(productHome.includes("Explore History"), false);
  assert.equal(productHome.includes("/reports"), false);
});

test("final Run Analysis CTA remains available", () => {
  assert.match(productHome, /Ready to generate a fresh market analysis\?/);
  assert.match(productHome, /<RunAnalysisButton \/>/);
});

test("homepage leakage tests still pass", () => {
  for (const value of FORBIDDEN_VALUES) {
    assert.equal(homeTree.includes(value), false, value);
  }
  assert.equal(homeTree.includes("Overall Market State"), false);
  assert.equal(homeTree.includes("Grounded AI Market Brief"), false);
});

test("dark-mode semantic tokens are used by new components", () => {
  for (const token of [
    "--surface",
    "--surface-elevated",
    "--text-primary",
    "--text-secondary",
    "--text-muted",
    "--border",
    "--quant-accent",
  ]) {
    assert.match(css, new RegExp(`\\.hero-preview[\\s\\S]*${token}|${token}[\\s\\S]*\\.hero-preview`));
  }
  assert.match(css, /\.hero-preview[\s\S]*var\(--surface\)/);
  assert.match(css, /\.capability-card[\s\S]*var\(--surface\)/);
  assert.match(css, /\.capability-icon[\s\S]*var\(--quant-accent\)/);
  assert.match(css, /\.pipeline-phase[\s\S]*var\(--text-primary\)/);
  assert.match(css, /\.hero-preview-card[\s\S]*var\(--text-primary\)/);
});

test("no chart or quantitative component is imported into homepage", () => {
  for (const name of ["BreadthChart", "TrendChart", "SectorChart", "Dashboard"]) {
    assert.equal(productHome.includes(name), false, name);
    assert.equal(homePage.includes(name), false, name);
    assert.equal(heroPreview.includes(name), false, name);
  }
});
