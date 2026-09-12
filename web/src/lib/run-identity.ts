import { randomBytes } from "node:crypto";

export const ACCESS_TOKEN_PATTERN = /^[a-f0-9]{64}$/;
export const RUN_ID_PATTERN =
  /^run-\d{8}-\d{6}-[a-f0-9]{4}$/;
export const RETENTION_MS = 7 * 24 * 60 * 60 * 1000;
export const STALE_LOCK_MS = 2 * 60 * 60 * 1000;

export function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

export function createRunId(now: Date = new Date()): string {
  const stamp =
    `${now.getUTCFullYear()}${pad2(now.getUTCMonth() + 1)}${pad2(now.getUTCDate())}` +
    `-${pad2(now.getUTCHours())}${pad2(now.getUTCMinutes())}${pad2(now.getUTCSeconds())}`;
  return `run-${stamp}-${randomBytes(2).toString("hex")}`;
}

export function createAccessToken(): string {
  return randomBytes(32).toString("hex");
}

export function isAccessToken(value: string): boolean {
  return ACCESS_TOKEN_PATTERN.test(value);
}

export function redactToken(token: string): string {
  if (token.length < 8) {
    return "[redacted]";
  }
  return `${token.slice(0, 4)}…${token.slice(-4)}`;
}

export function isoNow(now: Date = new Date()): string {
  return now.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function isExpired(createdAt: string, now: Date = new Date()): boolean {
  const created = Date.parse(createdAt);
  if (Number.isNaN(created)) {
    return true;
  }
  return now.getTime() - created >= RETENTION_MS;
}
