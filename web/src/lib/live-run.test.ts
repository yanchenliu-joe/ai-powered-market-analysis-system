import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { loadLiveRunSnapshot } from "./live-run-data.ts";
import { createVisitorAlias, writeReusableDaily } from "./run-access.ts";
import {
  ACCESS_TOKEN_PATTERN,
  createAccessToken,
  createRunId,
  isoNow,
} from "./run-identity.ts";
import { createQueuedManifest } from "./run-manifest.ts";
import { publicRunPolicy } from "./run-policy.ts";
import {
  analysisArtifactKey,
  analysisManifestKey,
  CONTROL_DAILY_QUOTA_KEY,
  LOCK_KEY,
  MemoryRunStore,
} from "./run-store.ts";
import { readRunManifest, readRunPdf, toPublicStatus } from "./run-status.ts";
import { executeRunTrigger } from "./run-trigger.ts";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");
const now = new Date("2026-09-12T16:00:00Z");
const policy = publicRunPolicy({
  PUBLIC_RUN_COOLDOWN_SECONDS: "900",
  PUBLIC_RUN_DAILY_QUOTA: "3",
  REPORT_ACCESS_TTL_SECONDS: "604800",
});

const configuredEnv = {
  GITHUB_TOKEN: "ghs_test",
  GITHUB_REPOSITORY: "owner/repo",
  BLOB_READ_WRITE_TOKEN: "vercel_blob_rw_test",
  PUBLIC_RUN_COOLDOWN_SECONDS: "900",
  PUBLIC_RUN_DAILY_QUOTA: "3",
};

function tokenA(): string {
  return "a".repeat(64);
}

function tokenB(): string {
  return "b".repeat(64);
}

async function seedReusable(
  store: MemoryRunStore,
  analysisId = "run-20260912-153422-a31f",
): Promise<void> {
  const manifest = createQueuedManifest(analysisId, "2026-09-12T15:00:00Z");
  manifest.status = "success";
  manifest.as_of_date = "2026-09-11";
  manifest.artifacts = {
    quant_summary: true,
    market_summary: true,
    breadth_timeseries: true,
    trend_timeseries: true,
    pdf: true,
  };
  await store.putText(analysisManifestKey(analysisId), JSON.stringify(manifest));
  await store.putText(
    analysisArtifactKey(analysisId, "quant_summary.json"),
    JSON.stringify({
      status: "success",
      run_metadata: {
        run_id: analysisId,
        as_of_date: "2026-09-11",
        generated_at: "2026-09-12T15:00:00Z",
      },
    }),
  );
  await store.putText(
    analysisArtifactKey(analysisId, "market_summary.json"),
    JSON.stringify({
      status: "available",
      run_id: analysisId,
      as_of_date: "2026-09-11",
    }),
  );
  await store.putBytes(
    analysisArtifactKey(analysisId, "market_report.pdf"),
    new TextEncoder().encode("%PDF-source"),
    "application/pdf",
  );
  await writeReusableDaily(store, {
    as_of_date: "2026-09-11",
    source_run_id: analysisId,
    analysis_id: analysisId,
    generated_at: "2026-09-12T15:00:00Z",
    status: "success",
  });
}

test("unconfigured infrastructure fails safely without a password", async () => {
  const result = await executeRunTrigger({ env: {}, now });
  assert.equal(result.status, 503);
  assert.equal(result.body.phase, "not_configured");
});

test("trigger generates distinct run_id and access_token", async () => {
  const store = new MemoryRunStore();
  const dispatched: Array<{ run_id: string; access_token: string }> = [];
  const result = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    clientHash: "client-a",
    dispatch: async (_repo, _token, _workflow, inputs) => {
      dispatched.push(inputs);
      return null;
    },
  });
  assert.equal(result.status, 202);
  assert.equal(result.body.reused, false);
  assert.ok(result.body.runId);
  assert.ok(result.body.token);
  assert.notEqual(result.body.runId, result.body.token);
  assert.match(result.body.runId ?? "", /^run-\d{8}-\d{6}-[a-f0-9]{4}$/);
  assert.match(result.body.token ?? "", ACCESS_TOKEN_PATTERN);
  assert.equal(dispatched.length, 1);
});

test("access token is cryptographically strong", () => {
  const tokens = new Set(Array.from({ length: 8 }, () => createAccessToken()));
  assert.equal(tokens.size, 8);
  for (const token of tokens) {
    assert.equal(token.length, 64);
    assert.match(token, ACCESS_TOKEN_PATTERN);
  }
  assert.notEqual(createRunId(), createAccessToken());
});

test("secrets are not returned from trigger", async () => {
  const store = new MemoryRunStore();
  const result = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    dispatch: async () => null,
  });
  const payload = JSON.stringify(result.body);
  assert.equal(payload.includes("ghs_test"), false);
  assert.equal(payload.includes("vercel_blob_rw_test"), false);
  assert.equal(payload.includes("OPENAI_API_KEY"), false);
});

test("queued analysis manifest is written before dispatch", async () => {
  const store = new MemoryRunStore();
  let sawManifest = false;
  await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    createIds: () => ({ runId: "run-20260912-153422-a31f", token: tokenA() }),
    dispatch: async () => {
      const text = await store.getText(analysisManifestKey("run-20260912-153422-a31f"));
      assert.ok(text);
      assert.equal(JSON.parse(text).status, "queued");
      sawManifest = true;
      return null;
    },
  });
  assert.equal(sawManifest, true);
});

test("reusable daily analysis prevents workflow dispatch", async () => {
  const store = new MemoryRunStore();
  await seedReusable(store);
  let dispatched = 0;
  const first = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    createIds: () => ({ token: tokenA() }),
    dispatch: async () => {
      dispatched += 1;
      return null;
    },
  });
  const second = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    createIds: () => ({ token: tokenB() }),
    dispatch: async () => {
      dispatched += 1;
      return null;
    },
  });
  assert.equal(dispatched, 0);
  assert.equal(first.body.reused, true);
  assert.equal(second.body.reused, true);
  assert.equal(first.body.runId, "run-20260912-153422-a31f");
  assert.equal(second.body.runId, "run-20260912-153422-a31f");
  assert.notEqual(first.body.token, second.body.token);
});

test("multiple reuse visitors do not consume new-run quota", async () => {
  const store = new MemoryRunStore();
  await seedReusable(store);
  await executeRunTrigger({ env: configuredEnv, store, now, dispatch: async () => null });
  await executeRunTrigger({ env: configuredEnv, store, now, dispatch: async () => null });
  const quota = JSON.parse((await store.getText(CONTROL_DAILY_QUOTA_KEY)) ?? "null");
  assert.equal(quota, null);
});

test("reused aliases resolve the same immutable source analysis", async () => {
  const store = new MemoryRunStore();
  await seedReusable(store, "run-source");
  const one = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    createIds: () => ({ token: tokenA() }),
    dispatch: async () => null,
  });
  const two = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    createIds: () => ({ token: tokenB() }),
    dispatch: async () => null,
  });
  const loadedA = await loadLiveRunSnapshot(store, one.body.token ?? "", now);
  const loadedB = await loadLiveRunSnapshot(store, two.body.token ?? "", now);
  assert.equal(loadedA.kind, "ok");
  assert.equal(loadedB.kind, "ok");
  if (loadedA.kind === "ok" && loadedB.kind === "ok") {
    assert.equal(loadedA.snapshot.quant?.run_metadata.run_id, "run-source");
    assert.equal(loadedB.snapshot.quant?.run_metadata.run_id, "run-source");
  }
});

test("no valid reuse dispatches a new run", async () => {
  const store = new MemoryRunStore();
  let dispatched = 0;
  const result = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    dispatch: async () => {
      dispatched += 1;
      return null;
    },
  });
  assert.equal(dispatched, 1);
  assert.equal(result.body.reused, false);
  assert.equal(result.body.phase, "queued");
});

test("cooldown blocks expensive duplicate request", async () => {
  const store = new MemoryRunStore();
  await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    clientHash: "same-client",
    dispatch: async () => null,
  });
  await store.putText(LOCK_KEY, JSON.stringify({ active: false, updated_at: isoNow(now) }));
  const blocked = await executeRunTrigger({
    env: configuredEnv,
    store,
    now: new Date("2026-09-12T16:05:00Z"),
    clientHash: "same-client",
    dispatch: async () => {
      throw new Error("should not dispatch");
    },
  });
  assert.equal(blocked.status, 429);
  assert.equal(blocked.body.phase, "rate_limited");
  assert.ok((blocked.body.retryAfterSeconds ?? 0) > 0);
});

test("quota blocks new computation after the daily limit", async () => {
  const store = new MemoryRunStore();
  await store.putText(
    CONTROL_DAILY_QUOTA_KEY,
    JSON.stringify({ utc_date: "2026-09-12", new_runs: 3 }),
  );
  const blocked = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    clientHash: "quota-client",
    dispatch: async () => {
      throw new Error("should not dispatch");
    },
  });
  assert.equal(blocked.status, 429);
  assert.equal(blocked.body.phase, "capacity_reached");
});

test("active computation does not create a duplicate workflow", async () => {
  const store = new MemoryRunStore();
  await store.putText(
    LOCK_KEY,
    JSON.stringify({
      active: true,
      run_id: "run-active",
      status: "running",
      created_at: isoNow(now),
      updated_at: isoNow(now),
    }),
  );
  await store.putText(
    analysisManifestKey("run-active"),
    JSON.stringify(createQueuedManifest("run-active", isoNow(now))),
  );
  let dispatched = 0;
  const joined = await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    createIds: () => ({ token: tokenA() }),
    dispatch: async () => {
      dispatched += 1;
      return null;
    },
  });
  assert.equal(dispatched, 0);
  assert.equal(joined.body.runId, "run-active");
  assert.equal(joined.body.phase, "queued");
});

test("raw IP is never stored", async () => {
  const store = new MemoryRunStore();
  await executeRunTrigger({
    env: configuredEnv,
    store,
    now,
    clientHash: "abc123hashed",
    dispatch: async () => null,
  });
  for (const [key, value] of store.objects) {
    const text = new TextDecoder().decode(value.body);
    assert.equal(text.includes("203.0.113.10"), false, key);
    assert.equal(key.includes("203.0.113.10"), false, key);
  }
});

test("unknown token 404", async () => {
  const store = new MemoryRunStore();
  assert.equal(await readRunManifest(store, tokenA(), now), "missing");
  assert.equal(await readRunManifest(store, "not-a-token", now), "invalid");
});

test("expired alias 404", async () => {
  const store = new MemoryRunStore();
  await seedReusable(store, "run-old");
  await createVisitorAlias(
    store,
    "run-old",
    new Date("2026-01-01T00:00:00Z"),
    { ...policy, accessTtlSeconds: 60 },
    true,
    tokenA(),
  );
  assert.equal(
    await readRunManifest(store, tokenA(), new Date("2026-01-01T00:02:00Z")),
    "expired",
  );
});

test("status reads the correct analysis manifest", async () => {
  const store = new MemoryRunStore();
  await seedReusable(store);
  await createVisitorAlias(store, "run-20260912-153422-a31f", now, policy, true, tokenA());
  const loaded = await readRunManifest(store, tokenA(), now);
  if (typeof loaded === "string") {
    assert.fail(loaded);
  }
  const publicStatus = toPublicStatus(tokenA(), loaded);
  assert.equal(publicStatus.runId, "run-20260912-153422-a31f");
  assert.equal(publicStatus.phase, "success");
});

test("report route cannot load another run without its token", async () => {
  const store = new MemoryRunStore();
  await seedReusable(store, "run-a");
  await createVisitorAlias(store, "run-a", now, policy, true, tokenA());
  const other = await loadLiveRunSnapshot(store, tokenB(), now);
  assert.equal(other.kind, "missing");
  const same = await loadLiveRunSnapshot(store, tokenA(), now);
  assert.equal(same.kind, "ok");
});

test("PDF alias resolves the immutable source PDF", async () => {
  const store = new MemoryRunStore();
  await seedReusable(store, "run-a");
  await createVisitorAlias(store, "run-a", now, policy, true, tokenA());
  await createVisitorAlias(store, "run-a", now, policy, true, tokenB());
  const pdf = await readRunPdf(store, tokenA(), now);
  assert.ok(pdf instanceof Uint8Array);
  assert.equal(new TextDecoder().decode(pdf), "%PDF-source");
});

test("live PDF path is not the global sample PDF", () => {
  const route = readFileSync(
    path.join(root, "src/app/api/runs/[token]/pdf/route.ts"),
    "utf8",
  );
  assert.equal(route.includes("/data/market_report.pdf"), false);
});

test("no report-history or bucket-listing endpoint", () => {
  assert.equal(
    readFileSync(path.join(root, "src/app/api/run-analysis/route.ts"), "utf8").includes(
      "list(",
    ),
    false,
  );
  assert.equal(readFileSync(path.join(root, "src/lib/run-trigger.ts"), "utf8").includes("/reports"), false);
});
