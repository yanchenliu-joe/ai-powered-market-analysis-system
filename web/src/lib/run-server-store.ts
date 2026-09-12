import type { RunObjectStore } from "./run-store.ts";

export async function createServerRunStore(
  env: NodeJS.ProcessEnv = process.env,
): Promise<RunObjectStore | null> {
  const token = env.BLOB_READ_WRITE_TOKEN;
  if (!token) {
    return null;
  }
  const { createVercelBlobStore } = await import("./vercel-blob-store.ts");
  return createVercelBlobStore(token);
}
