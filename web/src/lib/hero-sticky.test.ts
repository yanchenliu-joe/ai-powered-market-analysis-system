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
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const modal = readFileSync(path.join(root, "src/components/RunAnalysisModal.tsx"), "utf8");
const trigger = readFileSync(path.join(root, "src/lib/run-trigger.ts"), "utf8");
const homeTree = `${homePage}\n${productHome}\n${heroPreview}`;

test("desktop Hero copy uses position: sticky", () => {
  assert.match(css, /@media \(min-width:\s*901px\)[\s\S]*\.home-hero-copy-sticky[\s\S]*position:\s*sticky/);
  assert.match(productHome, /home-hero-copy-sticky/);
  assert.match(productHome, /home-hero-copy-inner/);
});

test("desktop top offset exists", () => {
  assert.match(css, /top:\s*clamp\(170px,\s*20vh,\s*220px\)/);
});

test("hero uses simple start-aligned grid columns", () => {
  assert.match(productHome, /home-hero-left/);
  assert.match(productHome, /home-hero-right/);
  assert.match(productHome, /home-hero-engine/);
  assert.match(css, /\.home-hero-split[\s\S]*align-items:\s*start/);
  assert.doesNotMatch(css, /top:\s*52vh/);
  assert.doesNotMatch(css, /translateY\(-50%\)/);
  assert.doesNotMatch(css, /margin-top:\s*calc\(52vh/);
  assert.doesNotMatch(css, /\.home-hero-copy-sticky[\s\S]{0,160}(?:^|[^a-z-])height:\s*0;/);
});

test("hero parent does not use fixed positioning for copy", () => {
  assert.equal(/home-hero-copy[\w-]*[\s\S]{0,160}position:\s*fixed/.test(css), false);
  assert.equal(productHome.includes("position: fixed"), false);
});

test("hero has explicit bottom containment / spacing", () => {
  assert.match(css, /\.home-hero\s*\{[\s\S]*?padding-bottom:\s*4\.5rem/);
  assert.doesNotMatch(css, /\.home-hero\s*\{[\s\S]*?padding-bottom:\s*clamp\(13rem/);
  assert.match(css, /@media \(max-width:\s*900px\)[\s\S]*?\.home-hero\s*\{[\s\S]*?padding-bottom:\s*4rem/);
});

test("mobile/tablet Hero copy is static", () => {
  assert.match(
    css,
    /@media \(max-width:\s*900px\)[\s\S]*\.home-hero-copy[\s\S]*position:\s*static/,
  );
});

test("Analysis Engine remains normal flow", () => {
  assert.match(productHome, /home-hero-engine/);
  assert.equal(heroPreview.includes("overflow-y"), false);
  assert.doesNotMatch(css, /\.home-hero-engine[\s\S]{0,80}overflow-y:\s*(auto|scroll)/);
});

test("How It Works click interaction remains", () => {
  const howItWorks = readFileSync(
    path.join(root, "src/components/HowItWorksPipeline.tsx"),
    "utf8",
  );
  assert.match(howItWorks, /Click to view details →/);
  assert.match(howItWorks, /Click to return ←/);
  assert.match(howItWorks, /onClick/);
  assert.equal(howItWorks.includes("onMouseEnter"), false);
});

test("Capabilities remains outside hero", () => {
  const heroClose = productHome.indexOf("</section>");
  const capabilities = productHome.indexOf('id="product"');
  assert.ok(heroClose > 0 && capabilities > heroClose);
  assert.match(productHome, /02 \/ Capabilities/);
});

test("no negative margin is used to hide overlap", () => {
  const heroBlock = css.match(/\.home-hero\s*\{[^}]+\}/)?.[0] ?? "";
  const sectionBlock = css.match(/\.home-section\s*\{[^}]+\}/g)?.join("\n") ?? "";
  assert.doesNotMatch(heroBlock, /margin(?:-top|-bottom)?:\s*-/);
  assert.doesNotMatch(sectionBlock, /margin(?:-top|-bottom)?:\s*-/);
});

test("no absolute-position hack", () => {
  assert.doesNotMatch(css, /\.home-hero-copy-inner[\s\S]{0,80}position:\s*absolute/);
  assert.doesNotMatch(css, /#product[\s\S]{0,120}position:\s*absolute/);
  assert.doesNotMatch(productHome, /position:\s*absolute/);
});

test("mobile does not inherit excessive desktop spacer", () => {
  assert.match(css, /@media \(max-width:\s*900px\)[\s\S]*\.home-hero\s*\{[\s\S]*padding-bottom:\s*4rem/);
  assert.doesNotMatch(
    css,
    /@media \(max-width:\s*900px\)[\s\S]*\.home-hero\s*\{[\s\S]*padding-bottom:\s*clamp\(5rem/,
  );
});

test("Analysis Engine does not use an internal scrolling container", () => {
  assert.equal(heroPreview.includes("overflow-y"), false);
  assert.equal(/\.hero-preview[\s\S]{0,240}overflow-y:\s*scroll/.test(css), false);
});

test("shared/global stage detail panel is removed", () => {
  assert.equal(heroPreview.includes('className="hero-preview-detail"'), false);
  assert.equal(heroPreview.includes("aria-live"), false);
});

test("each stage contains its own detail content", () => {
  assert.match(heroPreview, /hero-preview-detail-list/);
  for (const item of [
    "Daily U.S. equity prices",
    "Typed schemas",
    "Validated evidence only",
    "Interactive analysis",
  ]) {
    assert.match(heroPreview, new RegExp(item));
  }
});

test("hero stage details are static in document flow", () => {
  assert.doesNotMatch(css, /\.hero-preview-card-detail[\s\S]*position:\s*absolute/);
  assert.match(css, /\.hero-preview-card[\s\S]*min-height:\s*9\.5rem/);
  assert.match(css, /\.hero-preview-card[\s\S]*cursor:\s*default/);
});

test("all five stages preserve fixed/stable geometry", () => {
  assert.match(css, /\.hero-preview-card[\s\S]*max-height:\s*9\.5rem/);
  for (const stage of ["MARKET DATA", "QUANT ENGINE", "VALIDATION", "GROUNDED AI", "REPORT"]) {
    assert.match(heroPreview, new RegExp(stage));
  }
});

test("hero stages have no reveal interaction", () => {
  assert.equal(heroPreview.includes("onMouseEnter"), false);
  assert.equal(heroPreview.includes("onFocus"), false);
  assert.equal(heroPreview.includes("onClick"), false);
  assert.equal(heroPreview.includes("data-expanded"), false);
  assert.equal(heroPreview.includes("useState"), false);
  assert.equal(heroPreview.includes("<button"), false);
});

test("no API/fetch occurs from stage interaction", () => {
  assert.equal(heroPreview.includes("fetch("), false);
  assert.equal(heroPreview.includes("/api/"), false);
});

test("no analytical result is shown on homepage", () => {
  for (const value of ["38.1%", "58.5%", "-30.5 pp", "2.30", "Uptrend"]) {
    assert.equal(homeTree.includes(value), false, value);
  }
});

test("reduced-motion handling exists", () => {
  assert.match(css, /prefers-reduced-motion[\s\S]*\.pipeline-phase-front[\s\S]*transition:\s*none/);
});

test("CTA remains in hero", () => {
  assert.match(productHome, /HeroRunButton/);
  assert.match(productHome, /Free · No account required · Daily market analysis/);
});

test("current Swiss semantic colors remain", () => {
  for (const token of ["--nb-blue", "--nb-green", "--nb-violet", "--nb-orange", "--nb-yellow"]) {
    assert.match(css, new RegExp(token));
  }
});

test("report/live-run functionality is untouched", () => {
  assert.match(modal, /fetch\("\/api\/run-analysis"/);
  assert.match(trigger, /executeRunTrigger/);
  assert.equal(existsSync(path.join(root, "src/app/r/[token]/page.tsx")), true);
});
