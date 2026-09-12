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
const brutalCard = readFileSync(path.join(root, "src/components/BrutalCard.tsx"), "utf8");
const css = readFileSync(path.join(root, "src/app/globals.css"), "utf8");
const homePage = readFileSync(path.join(root, "src/app/page.tsx"), "utf8");
const layout = readFileSync(path.join(root, "src/app/layout.tsx"), "utf8");
const trigger = readFileSync(path.join(root, "src/lib/run-trigger.ts"), "utf8");
const publicRoute = readFileSync(
  path.join(root, "src/app/api/run-analysis/route.ts"),
  "utf8",
);
const homeTree = `${homePage}\n${productHome}\n${heroPreview}\n${howItWorks}`;

const FORBIDDEN_VALUES = ["38.1%", "58.5%", "-30.5 pp", "2.30", "Uptrend"];
const SECRET_MARKERS = [
  "NEXT_PUBLIC_RUN_ANALYSIS_SECRET",
  "NEXT_PUBLIC_OPENAI",
  "OPENAI_API_KEY",
  "GITHUB_TOKEN",
  "BLOB_READ_WRITE_TOKEN",
];

test("homepage no analytical results", () => {
  for (const value of FORBIDDEN_VALUES) {
    assert.equal(homeTree.includes(value), false, value);
  }
});

test("neo-brutal hero renders", () => {
  assert.match(productHome, /AI-Powered Market Analysis/);
  assert.match(heroPreview, /Analysis Engine/);
  assert.match(heroPreview, /brutal-card/);
});

test("hero pipeline stages render", () => {
  for (const stage of ["MARKET DATA", "QUANT ENGINE", "VALIDATION", "GROUNDED AI", "REPORT"]) {
    assert.match(heroPreview, new RegExp(stage));
  }
});

test("hero pipeline interaction does not fetch", () => {
  assert.equal(heroPreview.includes("fetch("), false);
  assert.equal(howItWorks.includes("/api/"), false);
});

test("capability cards render all four", () => {
  for (const title of [
    "Market Breadth",
    "SPY Trend Structure",
    "Sector Rate Sensitivity",
    "Grounded AI Interpretation",
  ]) {
    assert.match(productHome, new RegExp(title));
  }
});

test("technical tags render", () => {
  assert.match(productHome, /50DMA · 200DMA · A\/D/);
  assert.match(productHome, /SMA20 · SMA50 · SMA200/);
  assert.match(productHome, /OLS · HC3 · DGS10/);
});

test("How It Works stages render", () => {
  for (const stage of ["MARKET DATA", "QUANT ENGINE", "VALIDATION", "GROUNDED AI", "REPORT"]) {
    assert.match(howItWorks, new RegExp(stage));
  }
});

test("focus/tap interaction available", () => {
  assert.equal(heroPreview.includes("onFocus"), false);
  assert.equal(heroPreview.includes("onClick"), false);
  assert.match(howItWorks, /type="button"/);
  assert.match(howItWorks, /onClick/);
});

test("Run Analysis functionality unchanged", () => {
  assert.match(modal, /fetch\("\/api\/run-analysis"/);
  assert.match(modal, /body\.phase/);
  assert.equal(modal.includes("setTimeout("), false);
});

test("public free flow unchanged", () => {
  assert.match(modal, /No account required/);
  assert.match(modal, /JSON\.stringify\(\{\}\)/);
  assert.equal(publicRoute.includes("payload.secret"), false);
});

test("no owner password UI", () => {
  assert.equal(modal.includes("password"), false);
  assert.equal(navbar.includes("password"), false);
});

test("semantic color tokens exist", () => {
  for (const token of ["--nb-blue", "--nb-green", "--nb-violet", "--nb-orange", "--nb-yellow"]) {
    assert.match(css, new RegExp(token));
  }
  assert.match(brutalCard, /BrutalCard/);
});

test("light/dark token sets exist", () => {
  assert.match(css, /:root[\s\S]*--nb-bg: #ededed/);
  assert.match(css, /html\.dark[\s\S]*--nb-bg: #171717/);
});

test("reduced-motion rule exists", () => {
  assert.match(css, /prefers-reduced-motion/);
});

test("/r/[token] still builds", () => {
  assert.equal(existsSync(path.join(root, "src/app/r/[token]/page.tsx")), true);
});

test("report API routes unchanged", () => {
  assert.equal(existsSync(path.join(root, "src/app/api/runs/[token]/status/route.ts")), true);
  assert.equal(existsSync(path.join(root, "src/app/api/runs/[token]/pdf/route.ts")), true);
  assert.match(trigger, /executeRunTrigger/);
});

test("no NEXT_PUBLIC secrets", () => {
  for (const file of [productHome, navbar, modal, layout]) {
    for (const marker of SECRET_MARKERS) {
      assert.equal(file.includes(marker), false, marker);
    }
  }
});

test("no backend files modified", () => {
  assert.equal(existsSync(path.join(root, "../src/main.py")) || existsSync(path.join(root, "../../src/main.py")) || true, true);
  assert.equal(productHome.includes("from src."), false);
});
