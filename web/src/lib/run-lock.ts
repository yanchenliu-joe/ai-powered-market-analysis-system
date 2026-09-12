import { isoNow, STALE_LOCK_MS } from "./run-identity.ts";
import {
  ACTIVE_RUN_STATUSES,
  type RunLock,
  type RunStatus,
} from "./run-manifest.ts";
import { LOCK_KEY, type RunObjectStore } from "./run-store.ts";

export function isActiveLock(lock: RunLock | null, now: Date): boolean {
  if (!lock?.active || !lock.created_at || !lock.status) {
    return false;
  }
  if (!ACTIVE_RUN_STATUSES.includes(lock.status)) {
    return false;
  }
  const created = Date.parse(lock.created_at);
  if (Number.isNaN(created)) {
    return false;
  }
  return now.getTime() - created < STALE_LOCK_MS;
}

export async function readLock(store: RunObjectStore): Promise<RunLock | null> {
  const text = await store.getText(LOCK_KEY);
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as RunLock;
  } catch {
    return null;
  }
}

export async function writeActiveLock(
  store: RunObjectStore,
  runId: string,
  status: RunStatus,
  now: Date,
): Promise<void> {
  const stamp = isoNow(now);
  const lock: RunLock = {
    active: true,
    run_id: runId,
    status,
    created_at: stamp,
    updated_at: stamp,
  };
  await store.putText(LOCK_KEY, JSON.stringify(lock));
}

export async function releaseLock(store: RunObjectStore, now: Date): Promise<void> {
  await store.putText(
    LOCK_KEY,
    JSON.stringify({ active: false, updated_at: isoNow(now) }),
  );
}
