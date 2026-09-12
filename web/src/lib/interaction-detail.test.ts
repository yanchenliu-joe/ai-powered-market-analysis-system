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
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const modal = readFileSync(path.join(root, "src/components/RunAnalysisModal.tsx"), "utf8");
const trigger = readFileSync(path.join(root, "src/lib/run-trigger.ts"), "utf8");
const homeTree = `${homePage}\n${productHome}\n${heroPreview}\n${howItWorks}`;

test("Hero details render as permanent bullet lists", () => {
  assert.match(heroPreview, /hero-preview-detail-list/);
  assert.match(css, /\.hero-preview-detail-list[\s\S]*list-style:\s*none/);
  assert.match(css, /\.hero-preview-detail-list li::before/);
  assert.equal(heroPreview.includes("useState"), false);
  assert.equal(heroPreview.includes("<button"), false);
});

test("All five hero stage bullet sets exist", () => {
  for (const item of [
    "Daily U.S. equity prices",
    "Treasury-yield observations",
    "Validated input handling",
    "Market breadth",
    "SPY trend structure",
    "HC3 sector-rate regressions",
    "Typed schemas",
    "Consistency checks",
    "Evidence pack",
    "Validated evidence only",
    "Structured interpretation",
    "No metric recomputation",
    "Interactive analysis",
    "Research narrative",
    "Downloadable PDF",
  ]) {
    assert.match(heroPreview, new RegExp(item.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("Hero card dimensions remain stable", () => {
  assert.match(css, /\.hero-preview-card[\s\S]*height:\s*9\.5rem/);
  assert.match(css, /\.hero-preview-card[\s\S]*min-height:\s*9\.5rem/);
  assert.match(css, /\.hero-preview-card[\s\S]*max-height:\s*9\.5rem/);
});

test("Hero has no reveal overlay or hover content switch", () => {
  assert.doesNotMatch(css, /\.hero-preview-card-detail[\s\S]{0,80}position:\s*absolute/);
  assert.doesNotMatch(css, /\.hero-preview-card:hover \.hero-preview-card-detail/);
  assert.doesNotMatch(css, /\.hero-preview-card:focus-visible \.hero-preview-card-detail/);
  assert.match(css, /\.hero-preview-card[\s\S]*cursor:\s*default/);
});

test("How It Works hover does not reveal details", () => {
  assert.equal(howItWorks.includes("onMouseEnter"), false);
  assert.equal(howItWorks.includes("pipeline-reveal"), false);
});

test("How It Works click reveals detail", () => {
  assert.match(howItWorks, /onClick/);
  assert.match(howItWorks, /setExpanded/);
  assert.match(howItWorks, /pipeline-phase-detail/);
});

test("Clicking same stage closes detail", () => {
  assert.match(howItWorks, /current === phase\.title \? null : phase\.title/);
});

test("Clicking another stage switches active stage", () => {
  assert.match(howItWorks, /current === phase\.title \? null : phase\.title/);
  assert.match(howItWorks, /useState<string \| null>\(null\)/);
});

test("Only one stage detail active at a time", () => {
  assert.match(howItWorks, /expanded === phase\.title/);
});

test("How It Works detail uses bullet points", () => {
  assert.match(howItWorks, /pipeline-detail-list/);
  for (const item of [
    "U.S. equity market data",
    "HC3 sector regressions",
    "QuantSummary validation",
    "Evidence grounding",
    "Run-scoped report access",
  ]) {
    assert.match(howItWorks, new RegExp(item));
  }
});

test("How It Works shows visible click hints", () => {
  assert.match(howItWorks, /Click to view details →/);
  assert.match(howItWorks, /Click to return ←/);
  assert.match(howItWorks, /pipeline-phase-hint/);
});

test("Front/back card dimensions remain stable", () => {
  assert.match(css, /\.pipeline-phase-card[\s\S]*height:\s*12\.75rem/);
  assert.match(css, /\.pipeline-phase-card[\s\S]*min-height:\s*12\.75rem/);
  assert.match(css, /\.pipeline-phase-card[\s\S]*max-height:\s*12\.75rem/);
  assert.match(css, /\.pipeline-phase-front[\s\S]*position:\s*absolute/);
  assert.match(css, /\.pipeline-phase-detail[\s\S]*position:\s*absolute/);
});

test("Arrow layout remains unchanged", () => {
  assert.match(howItWorks, /pipeline-phase-arrow/);
  assert.match(css, /\.pipeline-phases[\s\S]*grid-template-columns:\s*repeat\(5/);
});

test("Keyboard Enter/Space toggles", () => {
  assert.match(howItWorks, /type="button"/);
});

test("aria-expanded is correct", () => {
  assert.match(howItWorks, /aria-expanded=\{isOpen\}/);
  assert.equal(heroPreview.includes("aria-expanded"), false);
});

test("Mobile tap works", () => {
  assert.match(howItWorks, /onClick/);
  assert.equal(howItWorks.includes("onMouseEnter"), false);
});

test("reduced-motion support exists", () => {
  assert.match(
    css,
    /prefers-reduced-motion[\s\S]*\.pipeline-phase-front[\s\S]*transition:\s*none/,
  );
});

test("no API/fetch occurs from these interactions", () => {
  assert.equal(heroPreview.includes("fetch("), false);
  assert.equal(howItWorks.includes("fetch("), false);
  assert.equal(heroPreview.includes("/api/"), false);
  assert.equal(howItWorks.includes("/api/"), false);
});

test("homepage still contains no market-analysis results", () => {
  for (const value of ["38.1%", "58.5%", "-30.5 pp", "2.30", "Uptrend"]) {
    assert.equal(homeTree.includes(value), false, value);
  }
  assert.equal(homeTree.includes("Overall Market State"), false);
});

test("backend/report/live-run behavior untouched", () => {
  assert.match(modal, /fetch\("\/api\/run-analysis"/);
  assert.match(trigger, /executeRunTrigger/);
  assert.equal(existsSync(path.join(root, "src/app/r/[token]/page.tsx")), true);
});
