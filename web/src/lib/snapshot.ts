import type {
  BreadthTimeseries,
  DashboardSnapshot,
  MarketInterpretation,
  QuantSummary,
  SnapshotLoadError,
  SnapshotManifest,
  TrendTimeseries,
} from "@/types/market";

const IDENTITY_MESSAGE =
  "Snapshot identity is inconsistent. Artifacts do not share the same run_id and as-of date.";

function identityOf(runId: string, asOfDate: string): string {
  return `${runId}|${asOfDate}`;
}

export function snapshotIdentityKey(runId: string, asOfDate: string): string {
  return identityOf(runId, asOfDate);
}

export function collectIdentityErrors(input: {
  quant: QuantSummary | null;
  market: MarketInterpretation | null;
  manifest: SnapshotManifest | null;
  breadthSeries: BreadthTimeseries | null;
  trendSeries: TrendTimeseries | null;
}): SnapshotLoadError[] {
  const errors: SnapshotLoadError[] = [];
  if (input.quant === null) {
    return errors;
  }
  const expected = identityOf(
    input.quant.run_metadata.run_id,
    input.quant.run_metadata.as_of_date,
  );
  const checks: Array<[string, string | null]> = [
    [
      "snapshot_manifest.json",
      input.manifest
        ? identityOf(input.manifest.run_id, input.manifest.as_of_date)
        : null,
    ],
    [
      "market_summary.json",
      input.market ? identityOf(input.market.run_id, input.market.as_of_date) : null,
    ],
    [
      "breadth_timeseries.json",
      input.breadthSeries
        ? identityOf(input.breadthSeries.run_id, input.breadthSeries.as_of_date)
        : null,
    ],
    [
      "trend_timeseries.json",
      input.trendSeries
        ? identityOf(input.trendSeries.run_id, input.trendSeries.as_of_date)
        : null,
    ],
  ];
  for (const [file, actual] of checks) {
    if (actual !== null && actual !== expected) {
      errors.push({ file, message: IDENTITY_MESSAGE });
    }
  }
  return errors;
}

export function applySnapshotGuards(
  snapshot: DashboardSnapshot,
): DashboardSnapshot {
  const identityErrors = collectIdentityErrors(snapshot);
  const errors = [...snapshot.errors, ...identityErrors];
  const consistent = identityErrors.length === 0;
  return {
    ...snapshot,
    breadthSeries: consistent ? snapshot.breadthSeries : null,
    trendSeries: consistent ? snapshot.trendSeries : null,
    errors,
    snapshotConsistent: consistent,
  };
}
