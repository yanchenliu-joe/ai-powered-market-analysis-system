import assert from "node:assert/strict";
import test from "node:test";

import { loadLiveRunSnapshot } from "./live-run-data.ts";
import { createVisitorAlias, readReusableDaily, writeReusableDaily } from "./run-access.ts";
import { createQueuedManifest } from "./run-manifest.ts";
import { publicRunPolicy } from "./run-policy.ts";
import {
  analysisArtifactKey,
  analysisManifestKey,
  MemoryRunStore,
} from "./run-store.ts";
import { readRunManifest } from "./run-status.ts";
import { executeRunTrigger } from "./run-trigger.ts";

const policy = publicRunPolicy({
  REPORT_ACCESS_TTL_SECONDS: "604800",
  ANALYSIS_SESSION_COMPLETE_HOUR_ET: "16",
});

const configuredEnv = {
  GITHUB_TOKEN: "ghs_test",
  GITHUB_REPOSITORY: "owner/repo",
  BLOB_READ_WRITE_TOKEN: "vercel_blob_rw_test",
  REPORT_ACCESS_TTL_SECONDS: "604800",
  ANALYSIS_SESSION_COMPLETE_HOUR_ET: "16",
};

async function seedAnalysis(
  store: MemoryRunStore,
  analysisId: string,
  asOfDate: string,
  generatedAt: string,
): Promise<void> {
  const manifest = createQueuedManifest(analysisId, generatedAt);
  manifest.status = "success";
  manifest.as_of_date = asOfDate;
  await store.putText(analysisManifestKey(analysisId), JSON.stringify(manifest));
  await store.putText(
    analysisArtifactKey(analysisId, "quant_summary.json"),
    JSON.stringify({
      status: "success",
      run_metadata: {
        run_id: analysisId,
        as_of_date: asOfDate,
        generated_at: generatedAt,
      },
    }),
  );
  await store.putText(
    analysisArtifactKey(analysisId, "market_summary.json"),
    JSON.stringify({
      status: "available",
      run_id: analysisId,
      as_of_date: asOfDate,
    }),
  );
  await writeReusableDaily(store, {
    as_of_date: asOfDate,
    source_run_id: analysisId,
    analysis_id: analysisId,
    generated_at: generatedAt,
    status: "success",
  });
}

test("same completed trading session reuses the pointer", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-friday", "2026-09-11", "2026-09-11T20:40:00Z");
  const reusable = await readReusableDaily(
    store,
    new Date("2026-09-11T20:45:00Z"),
    policy,
  );
  assert.equal(reusable?.as_of_date, "2026-09-11");
});

test("weekend requests reuse Friday", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-friday", "2026-09-11", "2026-09-11T20:40:00Z");
  assert.ok(await readReusableDaily(store, new Date("2026-09-12T16:00:00Z"), policy));
  assert.ok(await readReusableDaily(store, new Date("2026-09-13T16:00:00Z"), policy));
});

test("Monday morning reuses Friday; Monday after close does not", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-friday", "2026-09-11", "2026-09-11T20:40:00Z");
  assert.ok(await readReusableDaily(store, new Date("2026-09-14T14:00:00Z"), policy));
  assert.equal(
    await readReusableDaily(store, new Date("2026-09-14T20:30:00Z"), policy),
    null,
  );
});

test("holiday Monday reuses the prior completed session", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-friday", "2026-01-16", "2026-01-16T21:00:00Z");
  const reusable = await readReusableDaily(
    store,
    new Date("2026-01-19T17:00:00Z"),
    policy,
  );
  assert.equal(reusable?.as_of_date, "2026-01-16");
});

test("stale bundle inside 7-day access TTL is not treated as fresh", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-old", "2026-09-04", "2026-09-11T20:40:00Z");
  const mondayAfterClose = new Date("2026-09-14T20:30:00Z");
  assert.equal(await readReusableDaily(store, mondayAfterClose, policy), null);
  let dispatched = 0;
  const result = await executeRunTrigger({
    env: configuredEnv,
    store,
    now: mondayAfterClose,
    dispatch: async () => {
      dispatched += 1;
      return null;
    },
  });
  assert.equal(dispatched, 1);
  assert.equal(result.body.reused, false);
});

test("old report URL still works after analysis is no longer reusable", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-friday", "2026-09-11", "2026-09-11T20:40:00Z");
  const token = "c".repeat(64);
  await createVisitorAlias(
    store,
    "run-friday",
    new Date("2026-09-11T21:00:00Z"),
    policy,
    true,
    token,
  );
  const mondayAfterClose = new Date("2026-09-14T20:30:00Z");
  assert.equal(await readReusableDaily(store, mondayAfterClose, policy), null);
  const loaded = await loadLiveRunSnapshot(store, token, mondayAfterClose);
  assert.equal(loaded.kind, "ok");
  if (loaded.kind === "ok") {
    assert.equal(loaded.snapshot.quant?.run_metadata.as_of_date, "2026-09-11");
    assert.equal(loaded.snapshot.quant?.run_metadata.run_id, "run-friday");
  }
});

test("expired report alias is 404 while freshness is independent", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-friday", "2026-09-11", "2026-09-11T20:40:00Z");
  const token = "d".repeat(64);
  await createVisitorAlias(
    store,
    "run-friday",
    new Date("2026-09-11T21:00:00Z"),
    { ...policy, accessTtlSeconds: 60 },
    true,
    token,
  );
  assert.equal(
    await readRunManifest(store, token, new Date("2026-09-11T21:02:00Z")),
    "expired",
  );
});

test("reuse does not fabricate a quantitative as_of_date", async () => {
  const store = new MemoryRunStore();
  await seedAnalysis(store, "run-friday", "2026-09-11", "2026-09-11T20:40:00Z");
  const reused = await executeRunTrigger({
    env: configuredEnv,
    store,
    now: new Date("2026-09-12T16:00:00Z"),
    createIds: () => ({ token: "e".repeat(64) }),
    dispatch: async () => {
      throw new Error("must not dispatch");
    },
  });
  const loaded = await loadLiveRunSnapshot(
    store,
    reused.body.token ?? "",
    new Date("2026-09-12T16:00:00Z"),
  );
  assert.equal(reused.body.reused, true);
  assert.equal(loaded.kind, "ok");
  if (loaded.kind === "ok") {
    assert.equal(loaded.snapshot.quant?.run_metadata.as_of_date, "2026-09-11");
  }
});
