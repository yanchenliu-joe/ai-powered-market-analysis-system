import { readFile } from "node:fs/promises";
import path from "node:path";

import { applySnapshotGuards } from "@/lib/snapshot";
import type {
  BreadthTimeseries,
  DashboardSnapshot,
  MarketInterpretation,
  QuantSummary,
  SnapshotLoadError,
  SnapshotManifest,
  TrendTimeseries,
} from "@/types/market";

/** Development/sample snapshot only. Live runs never write this directory. */
const DATA_DIR = path.join(process.cwd(), "public", "data");

async function readSnapshotFile<T>(
  filename: string,
  errors: SnapshotLoadError[],
): Promise<T | null> {
  const filePath = path.join(DATA_DIR, filename);
  try {
    const text = await readFile(filePath, "utf8");
    return JSON.parse(text) as T;
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT") {
      return null;
    }
    errors.push({
      file: filename,
      message: `Could not parse ${filename}.`,
    });
    return null;
  }
}

export async function loadDashboardSnapshot(): Promise<DashboardSnapshot> {
  const errors: SnapshotLoadError[] = [];
  const [quant, market, manifest, breadthSeries, trendSeries] = await Promise.all([
    readSnapshotFile<QuantSummary>("quant_summary.json", errors),
    readSnapshotFile<MarketInterpretation>("market_summary.json", errors),
    readSnapshotFile<SnapshotManifest>("snapshot_manifest.json", errors),
    readSnapshotFile<BreadthTimeseries>("breadth_timeseries.json", errors),
    readSnapshotFile<TrendTimeseries>("trend_timeseries.json", errors),
  ]);

  if (quant === null && !errors.some((item) => item.file === "quant_summary.json")) {
    errors.push({
      file: "quant_summary.json",
      message: "Quantitative snapshot file is not in this deployment.",
    });
  }
  if (
    market === null &&
    !errors.some((item) => item.file === "market_summary.json")
  ) {
    errors.push({
      file: "market_summary.json",
      message: "Interpretation snapshot file is not in this deployment.",
    });
  }

  return applySnapshotGuards({
    quant,
    market,
    manifest,
    breadthSeries,
    trendSeries,
    errors,
    snapshotConsistent: true,
  });
}
