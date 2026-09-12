export const RUN_MANIFEST_SCHEMA = "1.0.0";

export const RUN_STATUSES = [
  "queued",
  "running",
  "publishing",
  "success",
  "partial",
  "failure",
] as const;

export type RunStatus = (typeof RUN_STATUSES)[number];
export type InterpretationAvailability = "available" | "unavailable";

export interface RunArtifacts {
  quant_summary: boolean;
  market_summary: boolean;
  breadth_timeseries: boolean;
  trend_timeseries: boolean;
  pdf: boolean;
}

export interface RunManifest {
  schema_version: typeof RUN_MANIFEST_SCHEMA;
  run_id: string;
  created_at: string;
  updated_at: string;
  status: RunStatus;
  as_of_date: string | null;
  interpretation_status: InterpretationAvailability | null;
  message: string | null;
  artifacts: RunArtifacts;
}

export interface RunLock {
  active: boolean;
  run_id?: string;
  status?: RunStatus;
  created_at?: string;
  updated_at?: string;
}

export const ACTIVE_RUN_STATUSES: readonly RunStatus[] = [
  "queued",
  "running",
  "publishing",
];

export function emptyArtifacts(): RunArtifacts {
  return {
    quant_summary: false,
    market_summary: false,
    breadth_timeseries: false,
    trend_timeseries: false,
    pdf: false,
  };
}

export function createQueuedManifest(runId: string, createdAt: string): RunManifest {
  return {
    schema_version: RUN_MANIFEST_SCHEMA,
    run_id: runId,
    created_at: createdAt,
    updated_at: createdAt,
    status: "queued",
    as_of_date: null,
    interpretation_status: null,
    message: "Analysis may take a few minutes.",
    artifacts: emptyArtifacts(),
  };
}

export function parseManifest(value: unknown): RunManifest | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (record.schema_version !== RUN_MANIFEST_SCHEMA) {
    return null;
  }
  if (typeof record.run_id !== "string") {
    return null;
  }
  if (typeof record.created_at !== "string" || typeof record.updated_at !== "string") {
    return null;
  }
  if (!RUN_STATUSES.includes(record.status as RunStatus)) {
    return null;
  }
  return record as unknown as RunManifest;
}
