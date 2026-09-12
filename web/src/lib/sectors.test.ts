import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { displaySensitivityLabel } from "./format.ts";
import {
  SECTOR_ORDER,
  ZERO_REFERENCE,
  buildSectorPlotRows,
  displaySectorName,
  formatSectorTooltipLines,
  orderSectorRegressions,
  significanceGroupFromLabel,
} from "./sectors.ts";
import type { SectorRegressionSummary } from "../types/market.ts";

function sector(overrides: Partial<SectorRegressionSummary>): SectorRegressionSummary {
  return {
    ticker: "XLK",
    alpha: 0,
    beta_yield: -0.0701,
    beta_std_error: 0.03,
    beta_t_value: -2.3,
    p_value: 0.023,
    ci_95_lower: -0.1303,
    ci_95_upper: -0.0099,
    r_squared: 0.1,
    adjusted_r_squared: 0.09,
    n_obs: 252,
    start_date: "2025-01-02",
    end_date: "2026-09-11",
    effect_10bp: -0.00701,
    sensitivity_label: "negative_significant",
    status: "success",
    error_reason: null,
    ...overrides,
  };
}

test("sector order remains deterministic and is not sorted by beta", () => {
  const rows = [
    sector({ ticker: "XLK", beta_yield: -0.9 }),
    sector({ ticker: "XLC", beta_yield: 0.4 }),
    sector({ ticker: "XLU", beta_yield: 0.1 }),
    sector({ ticker: "XLE", beta_yield: -0.2 }),
  ];
  assert.deepEqual(
    orderSectorRegressions(rows).map((row) => row.ticker),
    ["XLC", "XLE", "XLK", "XLU"],
  );
  assert.deepEqual(SECTOR_ORDER, [
    "XLC",
    "XLY",
    "XLP",
    "XLE",
    "XLF",
    "XLV",
    "XLI",
    "XLK",
    "XLB",
    "XLRE",
    "XLU",
  ]);
});

test("beta and CI values are sourced directly from the snapshot row", () => {
  const source = sector();
  const [plot] = buildSectorPlotRows([source]);
  assert.equal(plot.beta_yield, source.beta_yield);
  assert.equal(plot.ci_95_lower, source.ci_95_lower);
  assert.equal(plot.ci_95_upper, source.ci_95_upper);
  assert.deepEqual(plot.ciError, [
    source.beta_yield! - source.ci_95_lower!,
    source.ci_95_upper! - source.beta_yield!,
  ]);
});

test("zero reference exists as a constant", () => {
  assert.equal(ZERO_REFERENCE, 0);
});

test("significance derives from the accepted label only", () => {
  assert.equal(significanceGroupFromLabel("negative_significant"), "significant");
  assert.equal(
    significanceGroupFromLabel("positive_not_significant"),
    "not_significant",
  );
  assert.equal(significanceGroupFromLabel("insufficient_data"), "insufficient");
  assert.equal(
    displaySensitivityLabel("negative_significant"),
    "Negative · Significant",
  );
});

test("insufficient sector is not plotted as zero", () => {
  const plot = buildSectorPlotRows([
    sector({
      ticker: "XLU",
      beta_yield: null,
      ci_95_lower: null,
      ci_95_upper: null,
      p_value: null,
      effect_10bp: null,
      sensitivity_label: "insufficient_data",
      status: "insufficient_data",
      n_obs: 10,
    }),
  ])[0];
  assert.equal(plot.beta_yield, undefined);
  assert.notEqual(plot.beta_yield, 0);
  assert.equal(plot.ciError, undefined);
  assert.deepEqual(formatSectorTooltipLines(plot), [
    "XLU — Utilities",
    "Significance: Insufficient Data",
  ]);
});

test("tooltip formatting uses display values only", () => {
  const plot = buildSectorPlotRows([sector()])[0];
  assert.deepEqual(formatSectorTooltipLines(plot), [
    "XLK — Technology",
    "Beta: -0.0701",
    "95% CI: [-0.1303, -0.0099]",
    "p-value: 0.023",
    "+10bp effect: -0.70%",
    "Significance: Negative · Significant",
    "Observations: 252",
  ]);
});

test("sector display-name mapping keeps the ticker", () => {
  assert.equal(displaySectorName("XLK"), "XLK — Technology");
  assert.equal(displaySectorName("XLC"), "XLC — Communication Services");
});

test("no frontend p-value significance recomputation", () => {
  const source = readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)), "sectors.ts"),
    "utf8",
  );
  assert.equal(source.includes("0.05"), false);
  assert.equal(source.includes("p_value <"), false);
  assert.equal(source.includes("p-value <"), false);
});
