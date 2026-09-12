import { DEFAULT_SESSION_COMPLETE_HOUR_ET } from "./market-session.ts";

export const DEFAULT_PUBLIC_RUN_COOLDOWN_SECONDS = 900;
export const DEFAULT_PUBLIC_RUN_DAILY_QUOTA = 3;
export const DEFAULT_REPORT_ACCESS_TTL_SECONDS = 604800;

export interface PublicRunPolicy {
  cooldownSeconds: number;
  dailyQuota: number;
  accessTtlSeconds: number;
  sessionCompleteHourEt: number;
}

function parsePositiveInt(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallback;
  }
  return parsed;
}

export function publicRunPolicy(
  env: NodeJS.ProcessEnv = process.env,
): PublicRunPolicy {
  return {
    cooldownSeconds: parsePositiveInt(
      env.PUBLIC_RUN_COOLDOWN_SECONDS,
      DEFAULT_PUBLIC_RUN_COOLDOWN_SECONDS,
    ),
    dailyQuota: parsePositiveInt(
      env.PUBLIC_RUN_DAILY_QUOTA,
      DEFAULT_PUBLIC_RUN_DAILY_QUOTA,
    ),
    accessTtlSeconds: parsePositiveInt(
      env.REPORT_ACCESS_TTL_SECONDS,
      DEFAULT_REPORT_ACCESS_TTL_SECONDS,
    ),
    sessionCompleteHourEt: parsePositiveInt(
      env.ANALYSIS_SESSION_COMPLETE_HOUR_ET,
      DEFAULT_SESSION_COMPLETE_HOUR_ET,
    ),
  };
}
