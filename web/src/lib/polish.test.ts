import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  displayEvidenceMetric,
  humanizeAiProse,
  uniqueLimitations,
} from "./dashboard-state.ts";
import { formatEvidenceValue } from "./format.ts";
import { SECTOR_ORDER, buildSectorPlotRows } from "./sectors.ts";
import type { EvidenceItem, QuantSummary } from "../types/market.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const dashboardSource = readFileSync(
  path.join(root, "src/components/Dashboard.tsx"),
  "utf8",
);
const reportSource = readFileSync(
  path.join(root, "src/components/ReportView.tsx"),
  "utf8",
);
const marketText = readFileSync(
  path.join(root, "public/data/market_summary.json"),
  "utf8",
);
const market = JSON.parse(marketText) as {
  evidence: EvidenceItem[];
  evidence_used: EvidenceItem[];
  executive_summary: string;
  sector_rate_risk: string;
};
const quant = JSON.parse(
  readFileSync(path.join(root, "public/data/quant_summary.json"), "utf8"),
) as QuantSummary;

test("XLF evidence metric identity remains XLF.sensitivity_label", () => {
  const xlf = market.evidence.find((item) => item.metric.includes("XLF"));
  assert.equal(xlf?.metric, "XLF.sensitivity_label");
  assert.equal(xlf?.value, "negative_not_significant");
  const xle = market.evidence.find((item) => item.metric.includes("XLE"));
  assert.equal(xle?.metric, "XLE.sensitivity_label");
  assert.equal(xle?.value, "positive_significant");
  assert.equal(displayEvidenceMetric("XLF.sensitivity_label"), "XLF.sensitivity_label");
});

test("evidence metrics are not humanized or renamed", () => {
  assert.equal(
    displayEvidenceMetric("XLF.sensitivity_label"),
    "XLF.sensitivity_label",
  );
  assert.equal(
    formatEvidenceValue("XLF.sensitivity_label", "negative_not_significant"),
    "Negative · Not Significant",
  );
  assert.equal(reportSource.includes("displayEvidenceMetric(item.metric)"), true);
  assert.equal(reportSource.includes("humanizeAiProse(item.metric)"), false);
});

test("sector table is inside collapsed details by default", () => {
  assert.equal(dashboardSource.includes("<details open"), false);
  assert.match(reportSource, /<summary>View evidence<\/summary>/);
});

test("all 11 sector rows remain present", () => {
  assert.equal(quant.sector_regressions.length, 11);
  assert.deepEqual(
    quant.sector_regressions.map((row) => row.ticker).sort(),
    [...SECTOR_ORDER].sort(),
  );
  assert.equal(reportSource.includes("{sectorRows.map((row) => ("), true);
});

test("survivorship-bias copy is displayed only once", () => {
  const displayed = uniqueLimitations(quant.limitations);
  const survivorship = displayed.filter((item) =>
    item.toLowerCase().includes("survivorship bias"),
  );
  assert.equal(survivorship.length, 1);
  assert.equal(
    survivorship[0],
    "Historical breadth uses the current S&P 500 constituent universe and is subject to survivorship bias because point-in-time membership is not used.",
  );
});

test("distinct methodology limitations remain", () => {
  const displayed = uniqueLimitations(quant.limitations).join(" ");
  assert.match(displayed, /association, not causation/i);
  assert.match(displayed, /one-factor/i);
  assert.match(displayed, /survivorship bias/i);
});

test("AI prose humanizes known sensitivity tokens", () => {
  assert.equal(
    humanizeAiProse("XLE the only positive_significant sector"),
    "XLE the only positive and statistically significant sector",
  );
  assert.equal(
    humanizeAiProse("mostly negative_significant across sectors"),
    "mostly negative and statistically significant across sectors",
  );
  assert.equal(
    humanizeAiProse("XLF is negative_not_significant"),
    "XLF is negative but not statistically significant",
  );
  assert.match(dashboardSource, /humanizeAiProse\(market\.executive_summary\)/);
  assert.match(reportSource, /humanizeAiProse\(market\?\.sector_rate_risk\)/);
});

test("raw market_summary data remains unchanged", () => {
  assert.match(marketText, /"metric": "XLF\.sensitivity_label"/);
  assert.match(marketText, /"metric": "XLE\.sensitivity_label"/);
  assert.match(market.executive_summary, /positive_significant/);
  assert.match(market.sector_rate_risk, /negative_significant/);
  assert.match(market.sector_rate_risk, /negative_not_significant/);
});

test("chart data and snapshot values remain unchanged", () => {
  const xlk = quant.sector_regressions.find((row) => row.ticker === "XLK");
  const plot = buildSectorPlotRows(quant.sector_regressions).find(
    (row) => row.ticker === "XLK",
  );
  assert.equal(plot?.beta_yield, xlk?.beta_yield);
  assert.equal(plot?.ci_95_lower, xlk?.ci_95_lower);
  assert.equal(plot?.ci_95_upper, xlk?.ci_95_upper);
  assert.equal(quant.breadth.pct_above_50dma, 38.12375249500998);
});
