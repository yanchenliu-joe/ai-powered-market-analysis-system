import { get, put } from "@vercel/blob";

import { type BlobAuth, blobCommandOptions } from "./blob-auth.ts";
import type { RunObjectStore } from "./run-store.ts";

export class VercelBlobStore implements RunObjectStore {
  constructor(private readonly auth: BlobAuth) {}

  async getText(key: string): Promise<string | null> {
    const bytes = await this.getBytes(key);
    if (!bytes) {
      return null;
    }
    return new TextDecoder().decode(bytes);
  }

  async getBytes(key: string): Promise<Uint8Array | null> {
    try {
      const result = await get(key, {
        access: "private",
        useCache: false,
        ...blobCommandOptions(this.auth),
      });
      if (!result || !("stream" in result) || !result.stream) {
        return null;
      }
      const response = new Response(result.stream as ReadableStream);
      return new Uint8Array(await response.arrayBuffer());
    } catch {
      return null;
    }
  }

  async putText(
    key: string,
    body: string,
    contentType = "application/json",
  ): Promise<void> {
    await put(key, body, {
      access: "private",
      addRandomSuffix: false,
      allowOverwrite: true,
      contentType,
      ...blobCommandOptions(this.auth),
    });
  }

  async putBytes(
    key: string,
    body: Uint8Array,
    contentType: string,
  ): Promise<void> {
    await put(key, Buffer.from(body), {
      access: "private",
      addRandomSuffix: false,
      allowOverwrite: true,
      contentType,
      ...blobCommandOptions(this.auth),
    });
  }
}

export function createVercelBlobStore(auth: BlobAuth): VercelBlobStore {
  return new VercelBlobStore(auth);
}
