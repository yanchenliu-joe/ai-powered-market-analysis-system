import { blobAuthFromEnv } from "./blob-auth.ts";
import type { RunObjectStore } from "./run-store.ts";

export async function createServerRunStore(
  env: NodeJS.ProcessEnv = process.env,
): Promise<RunObjectStore | null> {
  const auth = blobAuthFromEnv(env);
  if (!auth) {
    return null;
  }
  const { createVercelBlobStore } = await import("./vercel-blob-store.ts");
  return createVercelBlobStore(auth);
}
