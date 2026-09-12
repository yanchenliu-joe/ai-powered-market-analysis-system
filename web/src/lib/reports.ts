import type { DashboardSnapshot } from "../types/market";

export function reportIdentity(snapshot: DashboardSnapshot): {
  runId: string | null;
  asOfDate: string | null;
  generatedAt: string | null;
  status: string | null;
  quantStatus: string | null;
  interpretationStatus: string | null;
  schemaVersion: string | null;
} {
  return {
    runId: snapshot.quant?.run_metadata.run_id ?? snapshot.market?.run_id ?? null,
    asOfDate:
      snapshot.quant?.run_metadata.as_of_date ?? snapshot.market?.as_of_date ?? null,
    generatedAt:
      snapshot.quant?.run_metadata.generated_at ?? snapshot.market?.generated_at ?? null,
    status: snapshot.quant?.status ?? snapshot.manifest?.quant_status ?? null,
    quantStatus: snapshot.quant?.status ?? snapshot.manifest?.quant_status ?? null,
    interpretationStatus:
      snapshot.market?.status ?? snapshot.manifest?.interpretation_status ?? null,
    schemaVersion:
      snapshot.quant?.schema_version ??
      snapshot.quant?.run_metadata.schema_version ??
      snapshot.manifest?.schema_version ??
      null,
  };
}
