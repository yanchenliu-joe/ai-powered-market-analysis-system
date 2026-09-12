import { createHash, timingSafeEqual } from "node:crypto";

function digest(value: string): Buffer {
  return createHash("sha256").update(value).digest();
}

export function authorizeOwner(
  provided: unknown,
  expected: string | undefined,
): boolean {
  if (typeof provided !== "string" || provided.length === 0) {
    return false;
  }
  if (!expected) {
    return false;
  }
  return timingSafeEqual(digest(provided), digest(expected));
}

export function isGithubDispatchConfigured(env: NodeJS.ProcessEnv = process.env): boolean {
  return Boolean(
    env.GITHUB_TOKEN &&
      env.GITHUB_REPOSITORY &&
      (env.GITHUB_WORKFLOW || "run-market-analysis.yml"),
  );
}

export function githubDispatchReady(env: NodeJS.ProcessEnv = process.env): boolean {
  return Boolean(env.GITHUB_TOKEN && env.GITHUB_REPOSITORY);
}

export function blobStoreReady(env: NodeJS.ProcessEnv = process.env): boolean {
  return Boolean(env.BLOB_READ_WRITE_TOKEN);
}

export function liveRunInfrastructureReady(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return githubDispatchReady(env) && blobStoreReady(env);
}
