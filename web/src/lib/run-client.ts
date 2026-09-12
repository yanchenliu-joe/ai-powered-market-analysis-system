import { createHash } from "node:crypto";

export function clientIdentifierFromHeaders(
  headers: Headers | Record<string, string | undefined>,
): string | undefined {
  const read = (name: string): string | undefined => {
    if (headers instanceof Headers) {
      return headers.get(name) ?? undefined;
    }
    return headers[name];
  };
  const forwarded = read("x-forwarded-for")?.split(",")[0]?.trim();
  const vercel = read("x-vercel-forwarded-for")?.split(",")[0]?.trim();
  const real = read("x-real-ip")?.trim();
  return forwarded || vercel || real || undefined;
}

export function hashClientIdentifier(
  identifier: string | undefined,
  env: NodeJS.ProcessEnv = process.env,
): string {
  const salt = env.CLIENT_HASH_SALT ?? "";
  const value = identifier && identifier.length > 0 ? identifier : "unknown";
  return createHash("sha256").update(`${salt}:${value}`).digest("hex");
}

export function assertNoRawIp(payload: string): boolean {
  return !/\b\d{1,3}(?:\.\d{1,3}){3}\b/.test(payload);
}
