import { get, put } from "@vercel/blob";

import type { RunObjectStore } from "./run-store.ts";

export class VercelBlobStore implements RunObjectStore {
  constructor(private readonly token: string) {}

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
        token: this.token,
        useCache: false,
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
      token: this.token,
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
      token: this.token,
    });
  }
}

export function createVercelBlobStore(token: string): VercelBlobStore {
  return new VercelBlobStore(token);
}
