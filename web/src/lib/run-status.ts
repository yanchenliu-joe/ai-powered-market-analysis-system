import {
  readAccessAlias,
  readAnalysisManifest,
  isTimestampExpired,
} from "./run-access.ts";
import type { RunManifest } from "./run-manifest.ts";
import { analysisArtifactKey, type RunObjectStore } from "./run-store.ts";

export interface PublicRunStatus {
  runId: string;
  phase: RunManifest["status"];
  message: string | null;
  reportUrl: string | null;
  downloadUrl?: string | null;
  reused?: boolean;
}

export async function resolveTokenAccess(
  store: RunObjectStore,
  token: string,
  now: Date = new Date(),
): Promise<
  | { kind: "ok"; analysisId: string; manifest: RunManifest; reused: boolean }
  | "invalid"
  | "missing"
  | "expired"
> {
  const alias = await readAccessAlias(store, token);
  if (!alias) {
    return token.length === 64 ? "missing" : "invalid";
  }
  if (isTimestampExpired(alias.expires_at, now)) {
    return "expired";
  }
  const manifest = await readAnalysisManifest(store, alias.analysis_id);
  if (!manifest) {
    return "missing";
  }
  return {
    kind: "ok",
    analysisId: alias.analysis_id,
    manifest,
    reused: alias.reused,
  };
}

export async function readRunManifest(
  store: RunObjectStore,
  token: string,
  now: Date = new Date(),
): Promise<"invalid" | "missing" | "expired" | RunManifest> {
  const resolved = await resolveTokenAccess(store, token, now);
  if (resolved === "invalid" || resolved === "missing" || resolved === "expired") {
    return resolved;
  }
  return resolved.manifest;
}

export function toPublicStatus(
  token: string,
  manifest: RunManifest,
): PublicRunStatus {
  const complete =
    manifest.status === "success" || manifest.status === "partial";
  return {
    runId: manifest.run_id,
    phase: manifest.status,
    message: manifest.message,
    reportUrl: complete ? `/r/${token}` : null,
    downloadUrl: complete ? `/api/runs/${token}/pdf` : null,
  };
}

export async function readRunPdf(
  store: RunObjectStore,
  token: string,
  now: Date = new Date(),
): Promise<Uint8Array | "missing" | "expired"> {
  const resolved = await resolveTokenAccess(store, token, now);
  if (resolved === "expired") {
    return "expired";
  }
  if (resolved === "invalid" || resolved === "missing") {
    return "missing";
  }
  const bytes = await store.getBytes(
    analysisArtifactKey(resolved.analysisId, "market_report.pdf"),
  );
  if (!bytes) {
    return "missing";
  }
  return bytes;
}
