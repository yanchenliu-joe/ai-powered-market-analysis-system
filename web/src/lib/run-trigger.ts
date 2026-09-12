import type { PipelinePhase, RunAnalysisResponse } from "./pipeline.ts";
import {
  createVisitorAlias,
  readReusableDaily,
} from "./run-access.ts";
import { liveRunInfrastructureReady } from "./run-auth.ts";
import { createAccessToken, createRunId, isoNow, redactToken } from "./run-identity.ts";
import { isActiveLock, readLock, releaseLock, writeActiveLock } from "./run-lock.ts";
import { createQueuedManifest } from "./run-manifest.ts";
import { publicRunPolicy } from "./run-policy.ts";
import {
  cooldownRemainingSeconds,
  incrementDailyQuota,
  readCooldown,
  readDailyQuota,
  writeCooldown,
} from "./run-quota.ts";
import { analysisManifestKey, type RunObjectStore } from "./run-store.ts";

export interface GithubDispatch {
  (
    repository: string,
    token: string,
    workflow: string,
    inputs: { run_id: string; access_token: string },
  ): Promise<number | null>;
}

export interface RunTriggerInput {
  env?: NodeJS.ProcessEnv;
  store?: RunObjectStore;
  now?: Date;
  clientHash?: string;
  forceRefresh?: boolean;
  createIds?: () => { runId?: string; token: string };
  dispatch?: GithubDispatch;
}

function unconfigured(): { status: number; body: RunAnalysisResponse } {
  return {
    status: 503,
    body: {
      phase: "not_configured",
      configured: false,
      message: "Analysis is temporarily unavailable. Please try again later.",
    },
  };
}

async function defaultDispatch(
  repository: string,
  token: string,
  workflow: string,
  inputs: { run_id: string; access_token: string },
  env: NodeJS.ProcessEnv,
): Promise<number | null> {
  const response = await fetch(
    `https://api.github.com/repos/${repository}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        ref: env.GITHUB_REF || "main",
        inputs,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`GitHub dispatch failed with status ${response.status}`);
  }
  return null;
}

async function resolveStore(
  input: RunTriggerInput,
  env: NodeJS.ProcessEnv,
): Promise<RunObjectStore | null> {
  if (input.store) {
    return input.store;
  }
  const token = env.BLOB_READ_WRITE_TOKEN;
  if (!token) {
    return null;
  }
  const { createVercelBlobStore } = await import("./vercel-blob-store.ts");
  return createVercelBlobStore(token);
}

function readyResponse(
  analysisId: string,
  token: string,
  phase: "success" | "partial",
  reused: boolean,
): { status: number; body: RunAnalysisResponse } {
  return {
    status: 200,
    body: {
      phase,
      configured: true,
      reused,
      runId: analysisId,
      token,
      reportUrl: `/r/${token}`,
      downloadUrl: `/api/runs/${token}/pdf`,
      message: reused
        ? "Today's validated analysis is ready."
        : "Analysis complete.",
    },
  };
}

export async function executeRunTrigger(
  input: RunTriggerInput,
): Promise<{ status: number; body: RunAnalysisResponse }> {
  const env = input.env ?? process.env;
  const store = await resolveStore(input, env);
  if (!input.store && !liveRunInfrastructureReady(env)) {
    return unconfigured();
  }
  if (!store || !env.GITHUB_TOKEN || !env.GITHUB_REPOSITORY) {
    return unconfigured();
  }

  const now = input.now ?? new Date();
  const policy = publicRunPolicy(env);
  const forced = Boolean(input.forceRefresh);

  if (!forced) {
    const reusable = await readReusableDaily(store, now, policy);
    if (reusable) {
      const ids = input.createIds?.() ?? { token: createAccessToken() };
      const { token } = await createVisitorAlias(
        store,
        reusable.analysis_id,
        now,
        policy,
        true,
        ids.token,
      );
      console.info("live_run reused", {
        runId: reusable.source_run_id,
        token: redactToken(token),
        phase: reusable.status,
      });
      return readyResponse(reusable.source_run_id, token, reusable.status, true);
    }
  }

  const existing = await readLock(store);
  if (isActiveLock(existing, now) && existing?.run_id) {
    const ids = input.createIds?.() ?? { token: createAccessToken() };
    const { token } = await createVisitorAlias(
      store,
      existing.run_id,
      now,
      policy,
      false,
      ids.token,
    );
    console.info("live_run joined", {
      runId: existing.run_id,
      token: redactToken(token),
      phase: "queued",
    });
    return {
      status: 202,
      body: {
        phase: "queued" satisfies PipelinePhase,
        configured: true,
        reused: false,
        runId: existing.run_id,
        token,
        statusUrl: `/api/runs/${token}/status`,
        reportUrl: `/r/${token}`,
        message: "An analysis is already in progress. You can wait here for the report.",
      },
    };
  }

  if (!forced) {
    if (input.clientHash) {
      const remaining = cooldownRemainingSeconds(
        await readCooldown(store, input.clientHash),
        now,
        policy.cooldownSeconds,
      );
      if (remaining > 0) {
        return {
          status: 429,
          body: {
            phase: "rate_limited",
            configured: true,
            reused: false,
            retryAfterSeconds: remaining,
            message: "Please wait before requesting another fresh analysis.",
          },
        };
      }
    }

    const quota = await readDailyQuota(store, now);
    if (quota.new_runs >= policy.dailyQuota) {
      return {
        status: 429,
        body: {
          phase: "capacity_reached",
          configured: true,
          reused: false,
          message:
            "Today's new-analysis capacity has been reached. Please try again later.",
        },
      };
    }
  }

  const generated = input.createIds?.() ?? {
    runId: createRunId(now),
    token: createAccessToken(),
  };
  const runId = generated.runId ?? createRunId(now);
  const token = generated.token;
  const createdAt = isoNow(now);
  const manifest = createQueuedManifest(runId, createdAt);
  await store.putText(analysisManifestKey(runId), JSON.stringify(manifest));
  await createVisitorAlias(store, runId, now, policy, false, token);
  await writeActiveLock(store, runId, "queued", now);
  if (!forced) {
    await incrementDailyQuota(store, now);
    if (input.clientHash) {
      await writeCooldown(store, input.clientHash, now);
    }
  }

  const repository = env.GITHUB_REPOSITORY;
  const githubToken = env.GITHUB_TOKEN;
  const workflow = env.GITHUB_WORKFLOW || "run-market-analysis.yml";
  const dispatch =
    input.dispatch ??
    ((repo, ghToken, file, inputs) =>
      defaultDispatch(repo, ghToken, file, inputs, env));

  try {
    const githubRunId = await dispatch(repository, githubToken, workflow, {
      run_id: runId,
      access_token: token,
    });
    console.info("live_run queued", {
      runId,
      token: redactToken(token),
      phase: "queued",
    });
    return {
      status: 202,
      body: {
        phase: "queued" satisfies PipelinePhase,
        configured: true,
        reused: false,
        runId,
        token,
        statusUrl: `/api/runs/${token}/status`,
        reportUrl: `/r/${token}`,
        githubRunId: githubRunId ?? undefined,
        message: "Analysis typically takes a few minutes when a new daily run is required.",
      },
    };
  } catch {
    await store.putText(
      analysisManifestKey(runId),
      JSON.stringify({
        ...manifest,
        status: "failure",
        updated_at: isoNow(now),
        message: "Analysis dispatch failed.",
      }),
    );
    await releaseLock(store, now);
    return {
      status: 502,
      body: {
        phase: "failure",
        configured: true,
        reused: false,
        message: "Analysis could not be started. Please try again later.",
      },
    };
  }
}
