import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { assertNoRawIp, hashClientIdentifier } from "./run-client.ts";
import { PIPELINE_PHASES } from "./pipeline.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const modal = readFileSync(path.join(root, "src/components/RunAnalysisModal.tsx"), "utf8");
const productHome = readFileSync(path.join(root, "src/components/ProductHome.tsx"), "utf8");
const publicRoute = readFileSync(
  path.join(root, "src/app/api/run-analysis/route.ts"),
  "utf8",
);
const adminRoute = readFileSync(
  path.join(root, "src/app/api/admin/refresh-analysis/route.ts"),
  "utf8",
);

test("no password field or owner-only copy", () => {
  assert.equal(modal.includes("password"), false);
  assert.equal(modal.includes("Owner-only"), false);
  assert.equal(modal.includes("Owner authorization"), false);
  assert.equal(modal.includes("owner secret"), false);
  assert.equal(modal.includes("Request run"), false);
  assert.equal(productHome.includes("authorized owner"), false);
});

test("Start Analysis works without a secret", () => {
  assert.match(modal, /Start Analysis/);
  assert.match(modal, /JSON\.stringify\(\{\}\)/);
  assert.equal(publicRoute.includes("payload.secret"), false);
  assert.equal(publicRoute.includes("RUN_ANALYSIS_SECRET"), false);
  assert.match(publicRoute, /executeRunTrigger/);
});

test("no account required copy and reuse explanation", () => {
  assert.match(modal, /No account required/);
  assert.match(modal, /may be reused/);
  assert.match(modal, /analysis is ready/);
  assert.match(modal, /no duplicate pipeline run/);
});

test("reused response shows report and PDF actions", () => {
  assert.match(modal, /phase === "reused"/);
  assert.match(modal, /View Report/);
  assert.match(modal, /Download PDF/);
  assert.match(modal, /downloadUrl/);
  assert.match(modal, /reportUrl/);
});

test("rate-limited and capacity states are real", () => {
  assert.match(modal, /rate_limited/);
  assert.match(modal, /capacity_reached/);
  assert.match(modal, /Please wait before requesting another fresh analysis/);
  assert.match(modal, /new-analysis capacity has been reached/);
  assert.equal(PIPELINE_PHASES.includes("rate_limited"), true);
  assert.equal(PIPELINE_PHASES.includes("capacity_reached"), true);
});

test("queued running publishing states exist without fake progress", () => {
  for (const phase of ["checking", "queued", "running", "publishing", "reused"]) {
    assert.equal(PIPELINE_PHASES.includes(phase as never), true);
  }
  assert.match(modal, /POLL_PHASES/);
  assert.equal(modal.includes("setTimeout("), false);
  assert.equal(modal.includes("localStorage"), false);
});

test("client hashes do not persist raw IPs", () => {
  const hashed = hashClientIdentifier("203.0.113.10", { CLIENT_HASH_SALT: "salt" });
  assert.equal(hashed.includes("203.0.113.10"), false);
  assert.equal(assertNoRawIp(hashed), true);
});

test("enforcement variables stay server-side", () => {
  assert.equal(modal.includes("NEXT_PUBLIC_PUBLIC_RUN"), false);
  assert.equal(modal.includes("PUBLIC_RUN_DAILY_QUOTA"), false);
  assert.equal(modal.includes("OPENAI_API_KEY"), false);
  assert.equal(modal.includes("GITHUB_TOKEN"), false);
  assert.equal(modal.includes("BLOB_READ_WRITE_TOKEN"), false);
  assert.match(adminRoute, /authorizeOwner/);
  assert.match(adminRoute, /forceRefresh: true/);
});
