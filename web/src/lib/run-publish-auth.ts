import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

import { issueSignedToken, presignUrl } from "@vercel/blob";

import { blobAuthFromEnv, blobCommandOptions, publicAppUrl } from "./blob-auth.ts";
import { analysisArtifactKey, type RunObjectStore } from "./run-store.ts";

export const RUN_PUBLISH_TTL_MS = 45 * 60 * 1000;

export const RUN_PUBLISH_FILES = [
  "manifest.json",
  "quant_summary.json",
  "market_summary.json",
  "breadth_timeseries.json",
  "trend_timeseries.json",
  "market_report.pdf",
  "market_report.md",
  "breadth_timeseries.png",
  "spy_trend.png",
  "sector_rate_beta.png",
] as const;

export type RunPublishFile = (typeof RUN_PUBLISH_FILES)[number];

export interface RunPublishAuthorization {
  schema_version: "1.0.0";
  run_id: string;
  created_at: string;
  valid_until: number;
  uploads: Record<string, string>;
  finalize_url: string;
  finalize_nonce: string;
}

export interface FinalizeRecord {
  run_id: string;
  nonce_hash: string;
  expires_at: number;
  consumed?: boolean;
}

export type IssueRunUploadUrls = (
  runId: string,
  pathnames: string[],
  validUntil: number,
) => Promise<Record<string, string>>;

export function finalizeRecordKey(runId: string): string {
  return `control/finalize/${runId}.json`;
}

export function hashFinalizeNonce(nonce: string): string {
  return createHash("sha256").update(nonce).digest("hex");
}

export function analysisPathForRun(runId: string, filename: string): string {
  return analysisArtifactKey(runId, filename);
}

export function assertRunScopedPathname(runId: string, pathname: string): string {
  const prefix = `analysis/${runId}/`;
  if (!pathname.startsWith(prefix) || pathname.includes("..")) {
    throw new Error("publish path is outside the current run prefix");
  }
  const name = pathname.slice(prefix.length);
  if (!RUN_PUBLISH_FILES.includes(name as RunPublishFile) || name.includes("/")) {
    throw new Error("publish path is not an allowed run artifact");
  }
  return pathname;
}

export function isPublishAuthorizationExpired(
  authorization: Pick<RunPublishAuthorization, "valid_until">,
  now: Date = new Date(),
): boolean {
  return now.getTime() >= authorization.valid_until;
}

export function parseRunPublishAuthorization(
  value: unknown,
): RunPublishAuthorization | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (record.schema_version !== "1.0.0" || typeof record.run_id !== "string") {
    return null;
  }
  if (typeof record.valid_until !== "number" || typeof record.finalize_url !== "string") {
    return null;
  }
  if (typeof record.finalize_nonce !== "string" || !record.uploads || typeof record.uploads !== "object") {
    return null;
  }
  return {
    schema_version: "1.0.0",
    run_id: record.run_id,
    created_at:
      typeof record.created_at === "string"
        ? record.created_at
        : new Date().toISOString(),
    valid_until: record.valid_until,
    uploads: record.uploads as Record<string, string>,
    finalize_url: record.finalize_url,
    finalize_nonce: record.finalize_nonce,
  };
}

export async function defaultIssueRunUploadUrls(
  runId: string,
  pathnames: string[],
  validUntil: number,
  env: NodeJS.ProcessEnv = process.env,
): Promise<Record<string, string>> {
  const auth = blobAuthFromEnv(env);
  if (!auth) {
    throw new Error("Blob store is not configured");
  }
  const options = blobCommandOptions(auth);
  const uploads: Record<string, string> = {};
  for (const pathname of pathnames) {
    assertRunScopedPathname(runId, pathname);
    const signed = await issueSignedToken({
      ...options,
      pathname,
      operations: ["put"],
      validUntil,
    });
    const { presignedUrl } = await presignUrl(signed, {
      operation: "put",
      pathname,
      access: "private",
      allowOverwrite: true,
      addRandomSuffix: false,
      validUntil,
    });
    uploads[pathname] = presignedUrl;
  }
  return uploads;
}

export async function createRunPublishAuthorization(
  runId: string,
  store: RunObjectStore,
  env: NodeJS.ProcessEnv = process.env,
  now: Date = new Date(),
  issueUrls: IssueRunUploadUrls = (id, paths, until) =>
    defaultIssueRunUploadUrls(id, paths, until, env),
): Promise<RunPublishAuthorization> {
  const validUntil = now.getTime() + RUN_PUBLISH_TTL_MS;
  const pathnames = RUN_PUBLISH_FILES.map((name) => analysisPathForRun(runId, name));
  for (const pathname of pathnames) {
    assertRunScopedPathname(runId, pathname);
  }
  const uploads = await issueUrls(runId, pathnames, validUntil);
  for (const pathname of Object.keys(uploads)) {
    assertRunScopedPathname(runId, pathname);
  }
  const finalizeUrlBase = publicAppUrl(env);
  if (!finalizeUrlBase) {
    throw new Error("APP_BASE_URL or Vercel URL is required to finalize a live run");
  }
  const finalizeNonce = randomBytes(32).toString("hex");
  const record: FinalizeRecord = {
    run_id: runId,
    nonce_hash: hashFinalizeNonce(finalizeNonce),
    expires_at: validUntil,
  };
  await store.putText(finalizeRecordKey(runId), JSON.stringify(record));
  return {
    schema_version: "1.0.0",
    run_id: runId,
    created_at: new Date(now).toISOString(),
    valid_until: validUntil,
    uploads,
    finalize_url: `${finalizeUrlBase}/api/internal/finalize-run`,
    finalize_nonce: finalizeNonce,
  };
}

export function verifyFinalizeNonce(
  record: FinalizeRecord,
  nonce: string,
  now: Date,
): boolean {
  if (record.consumed) {
    return false;
  }
  if (now.getTime() >= record.expires_at) {
    return false;
  }
  const actual = Buffer.from(hashFinalizeNonce(nonce), "hex");
  const expected = Buffer.from(record.nonce_hash, "hex");
  if (actual.length !== expected.length) {
    return false;
  }
  return timingSafeEqual(actual, expected);
}
