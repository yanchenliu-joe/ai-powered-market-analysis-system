import assert from "node:assert/strict";
import test from "node:test";

import {
  blobAuthFromEnv,
  blobStoreReady,
  publicAppUrl,
} from "./blob-auth.ts";
import { liveRunInfrastructureReady } from "./run-auth.ts";
import { finalizeLiveRun } from "./run-finalize.ts";
import {
  RUN_PUBLISH_TTL_MS,
  assertRunScopedPathname,
  createRunPublishAuthorization,
  finalizeRecordKey,
  hashFinalizeNonce,
  isPublishAuthorizationExpired,
} from "./run-publish-auth.ts";
import {
  CONTROL_REUSABLE_DAILY_KEY,
  LOCK_KEY,
  MemoryRunStore,
  analysisManifestKey,
} from "./run-store.ts";
import { createQueuedManifest } from "./run-manifest.ts";

const now = new Date("2026-09-12T16:00:00Z");

test("OIDC store id is enough for server Blob configuration", () => {
  assert.equal(blobStoreReady({ BLOB_STORE_ID: "store_abc" }), true);
  assert.deepEqual(blobAuthFromEnv({ BLOB_STORE_ID: "store_abc" }), {
    mode: "oidc",
    storeId: "store_abc",
    oidcToken: undefined,
  });
  assert.equal(blobStoreReady({}), false);
  assert.equal(
    liveRunInfrastructureReady({
      GITHUB_TOKEN: "ghs",
      GITHUB_REPOSITORY: "owner/repo",
      BLOB_STORE_ID: "store_abc",
    }),
    true,
  );
});

test("read-write token remains a local fallback", () => {
  assert.equal(blobAuthFromEnv({ BLOB_READ_WRITE_TOKEN: "rw" })?.mode, "token");
});

test("run-scoped publish authorization cannot target another run", async () => {
  const store = new MemoryRunStore();
  const authorization = await createRunPublishAuthorization(
    "run-a",
    store,
    { APP_BASE_URL: "https://app.example.test" },
    now,
    async (runId, pathnames) => {
      const uploads: Record<string, string> = {};
      for (const pathname of pathnames) {
        uploads[pathname] = `https://blob.example.test/${runId}/${pathname}`;
      }
      return uploads;
    },
  );
  assert.equal(authorization.run_id, "run-a");
  assert.equal(authorization.valid_until, now.getTime() + RUN_PUBLISH_TTL_MS);
  for (const pathname of Object.keys(authorization.uploads)) {
    assert.ok(pathname.startsWith("analysis/run-a/"));
    assert.equal(pathname.includes("analysis/run-b/"), false);
    assert.equal(pathname.startsWith("control/"), false);
  }
  assert.throws(() => assertRunScopedPathname("run-a", "analysis/run-b/manifest.json"));
  assert.throws(() => assertRunScopedPathname("run-a", "control/active_run.json"));
  assert.ok(await store.getText(finalizeRecordKey("run-a")));
});

test("publish authorization expiration fails closed", () => {
  assert.equal(
    isPublishAuthorizationExpired({ valid_until: now.getTime() - 1 }, now),
    true,
  );
  assert.equal(
    isPublishAuthorizationExpired({ valid_until: now.getTime() + 1 }, now),
    false,
  );
});

test("finalize writes reusable daily state and consumes the nonce", async () => {
  const store = new MemoryRunStore();
  const manifest = createQueuedManifest("run-final", now.toISOString());
  manifest.status = "success";
  manifest.as_of_date = "2026-09-11";
  await store.putText(analysisManifestKey("run-final"), JSON.stringify(manifest));
  await store.putText(LOCK_KEY, JSON.stringify({ active: true, run_id: "run-final" }));
  await store.putText(
    finalizeRecordKey("run-final"),
    JSON.stringify({
      run_id: "run-final",
      nonce_hash: hashFinalizeNonce("nonce-final"),
      expires_at: now.getTime() + 60_000,
    }),
  );
  const ok = await finalizeLiveRun(
    store,
    {
      run_id: "run-final",
      finalize_nonce: "nonce-final",
      status: "success",
      as_of_date: "2026-09-11",
    },
    now,
  );
  assert.equal(ok.ok, true);
  assert.ok(await store.getText(CONTROL_REUSABLE_DAILY_KEY));
  const replay = await finalizeLiveRun(
    store,
    { run_id: "run-final", finalize_nonce: "nonce-final" },
    now,
  );
  assert.equal(replay.ok, false);
});

test("expired finalize nonce fails closed", async () => {
  const store = new MemoryRunStore();
  await store.putText(
    finalizeRecordKey("run-expired"),
    JSON.stringify({
      run_id: "run-expired",
      nonce_hash: hashFinalizeNonce("nonce-old"),
      expires_at: now.getTime() - 1,
    }),
  );
  const result = await finalizeLiveRun(
    store,
    { run_id: "run-expired", finalize_nonce: "nonce-old" },
    now,
  );
  assert.equal(result.ok, false);
});

test("public app URL does not invent a host", () => {
  assert.equal(publicAppUrl({}), null);
  assert.equal(publicAppUrl({ APP_BASE_URL: "https://app.example/" }), "https://app.example");
});
