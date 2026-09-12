import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  expectedLatestCompletedSession,
  isAcceptedAsOfCurrent,
  isNyseTradingDay,
  previousNyseTradingDay,
} from "./market-session.ts";

const source = readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), "market-session.ts"),
  "utf8",
);

test("weekends are not trading sessions", () => {
  assert.equal(isNyseTradingDay("2026-09-11"), true);
  assert.equal(isNyseTradingDay("2026-09-12"), false);
  assert.equal(isNyseTradingDay("2026-09-13"), false);
  assert.equal(previousNyseTradingDay("2026-09-12"), "2026-09-11");
  assert.equal(previousNyseTradingDay("2026-09-13"), "2026-09-11");
});

test("same completed trading session is current", () => {
  const fridayAfterClose = new Date("2026-09-11T20:30:00Z");
  assert.equal(expectedLatestCompletedSession(fridayAfterClose), "2026-09-11");
  assert.equal(isAcceptedAsOfCurrent("2026-09-11", fridayAfterClose), true);
});

test("Saturday after Friday reuses Friday", () => {
  const saturday = new Date("2026-09-12T16:00:00Z");
  assert.equal(expectedLatestCompletedSession(saturday), "2026-09-11");
  assert.equal(isAcceptedAsOfCurrent("2026-09-11", saturday), true);
});

test("Sunday after Friday reuses Friday", () => {
  const sunday = new Date("2026-09-13T16:00:00Z");
  assert.equal(expectedLatestCompletedSession(sunday), "2026-09-11");
  assert.equal(isAcceptedAsOfCurrent("2026-09-11", sunday), true);
});

test("Monday before a newer completed session reuses Friday", () => {
  const mondayMorningEt = new Date("2026-09-14T14:00:00Z");
  assert.equal(expectedLatestCompletedSession(mondayMorningEt), "2026-09-11");
  assert.equal(isAcceptedAsOfCurrent("2026-09-11", mondayMorningEt), true);
});

test("Monday after a newer completed session is not Friday", () => {
  const mondayAfterCloseEt = new Date("2026-09-14T20:30:00Z");
  assert.equal(expectedLatestCompletedSession(mondayAfterCloseEt), "2026-09-14");
  assert.equal(isAcceptedAsOfCurrent("2026-09-11", mondayAfterCloseEt), false);
  assert.equal(isAcceptedAsOfCurrent("2026-09-14", mondayAfterCloseEt), true);
});

test("market holiday reuses the prior completed session", () => {
  const mlkMonday = new Date("2026-01-19T17:00:00Z");
  assert.equal(isNyseTradingDay("2026-01-19"), false);
  assert.equal(previousNyseTradingDay("2026-01-19"), "2026-01-16");
  assert.equal(expectedLatestCompletedSession(mlkMonday), "2026-01-16");
  assert.equal(isAcceptedAsOfCurrent("2026-01-16", mlkMonday), true);
});

test("helper does not fabricate quantitative artifact dates", () => {
  assert.equal(source.includes("as_of_date:"), false);
  assert.equal(source.includes("putText"), false);
  assert.equal(source.includes("quant_summary"), false);
});
