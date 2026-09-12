export const PIPELINE_PHASES = [
  "idle",
  "checking",
  "reused",
  "queued",
  "running",
  "publishing",
  "success",
  "partial",
  "rate_limited",
  "capacity_reached",
  "failure",
  "not_configured",
] as const;

export type PipelinePhase = (typeof PIPELINE_PHASES)[number];

export const PIPELINE_STEPS = [
  "Acquire market data",
  "Compute breadth and trend",
  "Estimate sector rate sensitivity",
  "Validate quantitative results",
  "Generate grounded AI interpretation",
  "Build your report",
] as const;

export const PIPELINE_STATUS_LABELS: Record<PipelinePhase, string> = {
  idle: "Ready",
  checking: "Checking today's analysis",
  reused: "Ready",
  queued: "Queued",
  running: "Running analysis",
  publishing: "Publishing report",
  success: "Complete",
  partial: "Partial",
  rate_limited: "Please wait",
  capacity_reached: "Capacity reached",
  failure: "Failed",
  not_configured: "Not configured",
};

export interface RunAnalysisResponse {
  phase: PipelinePhase;
  message: string;
  configured: boolean;
  reused?: boolean;
  runId?: string;
  token?: string;
  statusUrl?: string;
  reportUrl?: string;
  downloadUrl?: string;
  retryAfterSeconds?: number;
  githubRunId?: number;
}

export function snapshotRunStatus(quantStatus: string | undefined): "Success" | "Partial" | "Unavailable" {
  if (quantStatus === "success") return "Success";
  if (quantStatus === "partial") return "Partial";
  return "Unavailable";
}
