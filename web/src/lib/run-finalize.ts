import { writeReusableDaily } from "./run-access.ts";
import { isoNow } from "./run-identity.ts";
import { releaseLock } from "./run-lock.ts";
import { parseManifest, type RunStatus } from "./run-manifest.ts";
import {
  finalizeRecordKey,
  verifyFinalizeNonce,
  type FinalizeRecord,
} from "./run-publish-auth.ts";
import { analysisManifestKey, type RunObjectStore } from "./run-store.ts";

export interface FinalizeRunInput {
  run_id: string;
  finalize_nonce: string;
  status?: RunStatus;
  message?: string | null;
  as_of_date?: string | null;
  interpretation_status?: string | null;
  artifacts?: Record<string, boolean> | null;
}

export async function finalizeLiveRun(
  store: RunObjectStore,
  input: FinalizeRunInput,
  now: Date = new Date(),
): Promise<{ ok: true } | { ok: false; status: number; message: string }> {
  const text = await store.getText(finalizeRecordKey(input.run_id));
  if (!text) {
    return { ok: false, status: 404, message: "Finalize record was not found." };
  }
  let record: FinalizeRecord;
  try {
    record = JSON.parse(text) as FinalizeRecord;
  } catch {
    return { ok: false, status: 400, message: "Finalize record is unreadable." };
  }
  if (record.run_id !== input.run_id) {
    return { ok: false, status: 403, message: "Finalize record does not match run." };
  }
  if (!verifyFinalizeNonce(record, input.finalize_nonce, now)) {
    return { ok: false, status: 403, message: "Finalize authorization is invalid or expired." };
  }

  const manifestText = await store.getText(analysisManifestKey(input.run_id));
  let existing = null;
  if (manifestText) {
    try {
      existing = parseManifest(JSON.parse(manifestText));
    } catch {
      existing = null;
    }
  }
  const status = input.status ?? existing?.status ?? "failure";
  const asOf = input.as_of_date ?? existing?.as_of_date ?? null;
  if (status === "success" || status === "partial") {
    await writeReusableDaily(store, {
      as_of_date: asOf,
      source_run_id: input.run_id,
      analysis_id: input.run_id,
      generated_at: existing?.updated_at ?? isoNow(now),
      status,
    });
  }
  await releaseLock(store, now);
  await store.putText(
    finalizeRecordKey(input.run_id),
    JSON.stringify({ ...record, consumed: true }),
  );
  return { ok: true };
}
