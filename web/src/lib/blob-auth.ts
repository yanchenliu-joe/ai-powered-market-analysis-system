export type BlobAuth =
  | { mode: "token"; token: string }
  | { mode: "oidc"; storeId: string; oidcToken?: string };

export function blobAuthFromEnv(
  env: NodeJS.ProcessEnv = process.env,
): BlobAuth | null {
  if (env.BLOB_READ_WRITE_TOKEN) {
    return { mode: "token", token: env.BLOB_READ_WRITE_TOKEN };
  }
  if (env.BLOB_STORE_ID) {
    return {
      mode: "oidc",
      storeId: env.BLOB_STORE_ID,
      oidcToken: env.VERCEL_OIDC_TOKEN,
    };
  }
  return null;
}

export function blobCommandOptions(auth: BlobAuth): {
  token?: string;
  storeId?: string;
  oidcToken?: string;
} {
  if (auth.mode === "token") {
    return { token: auth.token };
  }
  return {
    storeId: auth.storeId,
    ...(auth.oidcToken ? { oidcToken: auth.oidcToken } : {}),
  };
}

export function blobStoreReady(env: NodeJS.ProcessEnv = process.env): boolean {
  return blobAuthFromEnv(env) !== null;
}

export function publicAppUrl(env: NodeJS.ProcessEnv = process.env): string | null {
  const explicit = env.APP_BASE_URL || env.VERCEL_BLOB_CALLBACK_URL;
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }
  if (env.VERCEL_PROJECT_PRODUCTION_URL) {
    return `https://${env.VERCEL_PROJECT_PRODUCTION_URL.replace(/\/$/, "")}`;
  }
  if (env.VERCEL_URL) {
    return `https://${env.VERCEL_URL.replace(/\/$/, "")}`;
  }
  return null;
}
