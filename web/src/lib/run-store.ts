export interface RunObjectStore {
  getText(key: string): Promise<string | null>;
  getBytes(key: string): Promise<Uint8Array | null>;
  putText(key: string, body: string, contentType?: string): Promise<void>;
  putBytes(key: string, body: Uint8Array, contentType: string): Promise<void>;
}

export class MemoryRunStore implements RunObjectStore {
  readonly objects = new Map<string, { body: Uint8Array; contentType: string }>();

  async getText(key: string): Promise<string | null> {
    const item = this.objects.get(key);
    if (!item) {
      return null;
    }
    return new TextDecoder().decode(item.body);
  }

  async getBytes(key: string): Promise<Uint8Array | null> {
    return this.objects.get(key)?.body ?? null;
  }

  async putText(
    key: string,
    body: string,
    contentType = "application/json",
  ): Promise<void> {
    this.objects.set(key, {
      body: new TextEncoder().encode(body),
      contentType,
    });
  }

  async putBytes(
    key: string,
    body: Uint8Array,
    contentType: string,
  ): Promise<void> {
    this.objects.set(key, { body, contentType });
  }
}

export function analysisPrefix(analysisId: string): string {
  return `analysis/${analysisId}`;
}

export function analysisManifestKey(analysisId: string): string {
  return `${analysisPrefix(analysisId)}/manifest.json`;
}

export function analysisArtifactKey(analysisId: string, name: string): string {
  return `${analysisPrefix(analysisId)}/${name}`;
}

export function accessAliasKey(token: string): string {
  return `access/${token}.json`;
}

export const CONTROL_ACTIVE_RUN_KEY = "control/active_run.json";
export const CONTROL_DAILY_QUOTA_KEY = "control/daily_quota.json";
export const CONTROL_REUSABLE_DAILY_KEY = "control/reusable_daily.json";

export function cooldownKey(clientHash: string): string {
  return `control/cooldowns/${clientHash}.json`;
}

/** @deprecated Prefer CONTROL_ACTIVE_RUN_KEY. Kept as a lock alias. */
export const LOCK_KEY = CONTROL_ACTIVE_RUN_KEY;
