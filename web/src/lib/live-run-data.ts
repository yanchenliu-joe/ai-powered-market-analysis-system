import type {
  BreadthTimeseries,
  DashboardSnapshot,
  MarketInterpretation,
  QuantSummary,
  SnapshotLoadError,
  TrendTimeseries,
} from "../types/market.ts";
import { applySnapshotGuards } from "./snapshot.ts";

import { resolveTokenAccess } from "./run-status.ts";
import { analysisArtifactKey, type RunObjectStore } from "./run-store.ts";

export type LiveRunLoadResult =
  | { kind: "ok"; snapshot: DashboardSnapshot }
  | { kind: "missing" }
  | { kind: "expired" };

async function readJson<T>(
  store: RunObjectStore,
  analysisId: string,
  name: string,
  errors: SnapshotLoadError[],
): Promise<T | null> {
  const text = await store.getText(analysisArtifactKey(analysisId, name));
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    errors.push({ file: name, message: `Could not parse ${name}.` });
    return null;
  }
}

export async function loadLiveRunSnapshot(
  store: RunObjectStore,
  token: string,
  now: Date = new Date(),
): Promise<LiveRunLoadResult> {
  const resolved = await resolveTokenAccess(store, token, now);
  if (resolved === "expired") {
    return { kind: "expired" };
  }
  if (resolved === "invalid" || resolved === "missing") {
    return { kind: "missing" };
  }
  if (resolved.manifest.status !== "success" && resolved.manifest.status !== "partial") {
    return { kind: "missing" };
  }

  const errors: SnapshotLoadError[] = [];
  const [quant, market, breadthSeries, trendSeries] = await Promise.all([
    readJson<QuantSummary>(store, resolved.analysisId, "quant_summary.json", errors),
    readJson<MarketInterpretation>(
      store,
      resolved.analysisId,
      "market_summary.json",
      errors,
    ),
    readJson<BreadthTimeseries>(
      store,
      resolved.analysisId,
      "breadth_timeseries.json",
      errors,
    ),
    readJson<TrendTimeseries>(
      store,
      resolved.analysisId,
      "trend_timeseries.json",
      errors,
    ),
  ]);

  if (!quant || !market) {
    return { kind: "missing" };
  }
  if (
    quant.run_metadata.run_id !== resolved.manifest.run_id ||
    (resolved.manifest.as_of_date &&
      quant.run_metadata.as_of_date !== resolved.manifest.as_of_date)
  ) {
    return { kind: "missing" };
  }

  const snapshot = applySnapshotGuards({
    quant,
    market,
    manifest: {
      schema_version: "1.0.0",
      generated_at: quant.run_metadata.generated_at,
      run_id: resolved.manifest.run_id,
      as_of_date: quant.run_metadata.as_of_date,
      quant_status: quant.status,
      interpretation_status: market.status,
      artifacts: {
        quant_summary: "quant_summary.json",
        market_summary: "market_summary.json",
        breadth_timeseries: "breadth_timeseries.json",
        trend_timeseries: "trend_timeseries.json",
      },
    },
    breadthSeries,
    trendSeries,
    errors,
    snapshotConsistent: true,
  });
  return { kind: "ok", snapshot };
}
