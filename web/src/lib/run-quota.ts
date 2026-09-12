import { isoNow } from "./run-identity.ts";
import {
  CONTROL_DAILY_QUOTA_KEY,
  cooldownKey,
  type RunObjectStore,
} from "./run-store.ts";

export interface DailyQuotaState {
  utc_date: string;
  new_runs: number;
}

export interface CooldownState {
  last_new_run_at: string;
}

export function utcDate(now: Date): string {
  return now.toISOString().slice(0, 10);
}

export async function readDailyQuota(
  store: RunObjectStore,
  now: Date,
): Promise<DailyQuotaState> {
  const today = utcDate(now);
  const text = await store.getText(CONTROL_DAILY_QUOTA_KEY);
  if (!text) {
    return { utc_date: today, new_runs: 0 };
  }
  try {
    const parsed = JSON.parse(text) as DailyQuotaState;
    if (parsed.utc_date !== today) {
      return { utc_date: today, new_runs: 0 };
    }
    return {
      utc_date: today,
      new_runs: Number.isFinite(parsed.new_runs) ? parsed.new_runs : 0,
    };
  } catch {
    return { utc_date: today, new_runs: 0 };
  }
}

export async function incrementDailyQuota(
  store: RunObjectStore,
  now: Date,
): Promise<DailyQuotaState> {
  const current = await readDailyQuota(store, now);
  const next = { utc_date: current.utc_date, new_runs: current.new_runs + 1 };
  await store.putText(CONTROL_DAILY_QUOTA_KEY, JSON.stringify(next));
  return next;
}

export async function readCooldown(
  store: RunObjectStore,
  clientHash: string,
): Promise<CooldownState | null> {
  const text = await store.getText(cooldownKey(clientHash));
  if (!text) {
    return null;
  }
  try {
    const parsed = JSON.parse(text) as CooldownState;
    if (typeof parsed.last_new_run_at !== "string") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function cooldownRemainingSeconds(
  state: CooldownState | null,
  now: Date,
  cooldownSeconds: number,
): number {
  if (!state) {
    return 0;
  }
  const last = Date.parse(state.last_new_run_at);
  if (Number.isNaN(last)) {
    return 0;
  }
  const elapsed = Math.floor((now.getTime() - last) / 1000);
  return Math.max(0, cooldownSeconds - elapsed);
}

export async function writeCooldown(
  store: RunObjectStore,
  clientHash: string,
  now: Date,
): Promise<void> {
  await store.putText(
    cooldownKey(clientHash),
    JSON.stringify({ last_new_run_at: isoNow(now) } satisfies CooldownState),
  );
}
