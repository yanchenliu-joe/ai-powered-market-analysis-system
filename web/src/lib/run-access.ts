import { isAcceptedAsOfCurrent } from "./market-session.ts";
import { createAccessToken, isoNow, isAccessToken } from "./run-identity.ts";
import { parseManifest, type RunManifest } from "./run-manifest.ts";
import type { PublicRunPolicy } from "./run-policy.ts";
import {
  accessAliasKey,
  analysisManifestKey,
  CONTROL_REUSABLE_DAILY_KEY,
  type RunObjectStore,
} from "./run-store.ts";

export interface AccessAlias {
  schema_version: "1.0.0";
  analysis_id: string;
  source_run_id: string;
  created_at: string;
  expires_at: string;
  reused: boolean;
}

export interface ReusableDaily {
  as_of_date: string | null;
  source_run_id: string;
  analysis_id: string;
  generated_at: string;
  status: "success" | "partial";
}

export function parseAccessAlias(value: unknown): AccessAlias | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (record.schema_version !== "1.0.0") {
    return null;
  }
  if (typeof record.analysis_id !== "string" || typeof record.source_run_id !== "string") {
    return null;
  }
  if (typeof record.created_at !== "string" || typeof record.expires_at !== "string") {
    return null;
  }
  return record as unknown as AccessAlias;
}

export function parseReusableDaily(value: unknown): ReusableDaily | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (typeof record.source_run_id !== "string" || typeof record.analysis_id !== "string") {
    return null;
  }
  if (typeof record.generated_at !== "string") {
    return null;
  }
  if (record.status !== "success" && record.status !== "partial") {
    return null;
  }
  return {
    as_of_date: typeof record.as_of_date === "string" ? record.as_of_date : null,
    source_run_id: record.source_run_id,
    analysis_id: record.analysis_id,
    generated_at: record.generated_at,
    status: record.status,
  };
}

export function aliasExpiresAt(now: Date, policy: PublicRunPolicy): string {
  return isoNow(new Date(now.getTime() + policy.accessTtlSeconds * 1000));
}

export function isTimestampExpired(stamp: string, now: Date): boolean {
  const parsed = Date.parse(stamp);
  if (Number.isNaN(parsed)) {
    return true;
  }
  return parsed <= now.getTime();
}

export async function writeAccessAlias(
  store: RunObjectStore,
  token: string,
  input: Omit<AccessAlias, "schema_version">,
): Promise<AccessAlias> {
  const alias: AccessAlias = { schema_version: "1.0.0", ...input };
  await store.putText(accessAliasKey(token), JSON.stringify(alias));
  return alias;
}

export async function createVisitorAlias(
  store: RunObjectStore,
  analysisId: string,
  now: Date,
  policy: PublicRunPolicy,
  reused: boolean,
  token: string = createAccessToken(),
): Promise<{ token: string; alias: AccessAlias }> {
  const created = isoNow(now);
  const alias = await writeAccessAlias(store, token, {
    analysis_id: analysisId,
    source_run_id: analysisId,
    created_at: created,
    expires_at: aliasExpiresAt(now, policy),
    reused,
  });
  return { token, alias };
}

export async function readAccessAlias(
  store: RunObjectStore,
  token: string,
): Promise<AccessAlias | null> {
  if (!isAccessToken(token)) {
    return null;
  }
  const text = await store.getText(accessAliasKey(token));
  if (!text) {
    return null;
  }
  try {
    return parseAccessAlias(JSON.parse(text));
  } catch {
    return null;
  }
}

export async function readAnalysisManifest(
  store: RunObjectStore,
  analysisId: string,
): Promise<RunManifest | null> {
  const text = await store.getText(analysisManifestKey(analysisId));
  if (!text) {
    return null;
  }
  try {
    return parseManifest(JSON.parse(text));
  } catch {
    return null;
  }
}

export async function readReusableDaily(
  store: RunObjectStore,
  now: Date,
  policy: PublicRunPolicy,
): Promise<ReusableDaily | null> {
  const text = await store.getText(CONTROL_REUSABLE_DAILY_KEY);
  if (!text) {
    return null;
  }
  let pointer: ReusableDaily | null = null;
  try {
    pointer = parseReusableDaily(JSON.parse(text));
  } catch {
    return null;
  }
  if (!pointer) {
    return null;
  }
  if (!pointer.as_of_date) {
    return null;
  }
  if (!isAcceptedAsOfCurrent(pointer.as_of_date, now, policy.sessionCompleteHourEt)) {
    return null;
  }
  const manifest = await readAnalysisManifest(store, pointer.analysis_id);
  if (!manifest) {
    return null;
  }
  if (manifest.status !== "success" && manifest.status !== "partial") {
    return null;
  }
  if (manifest.run_id !== pointer.source_run_id) {
    return null;
  }
  return pointer;
}

export async function writeReusableDaily(
  store: RunObjectStore,
  pointer: ReusableDaily,
): Promise<void> {
  await store.putText(CONTROL_REUSABLE_DAILY_KEY, JSON.stringify(pointer));
}
