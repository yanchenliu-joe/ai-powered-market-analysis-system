# v1.1 web data contract

The future Next.js dashboard consumes a static snapshot. The Python engine
remains the only analytics and OpenAI layer. The web layer must not recompute
breadth, moving averages, trend regimes, regressions, or interpretation.

Snapshot files live in `web/public/data/` and are produced by
`src/web_export.py` from already-validated objects and already-computed
timeseries DataFrames.

## Explicit export path

Normal CLI runs do **not** overwrite `web/public/data/`. Export happens only
when `--export-web-snapshot` is passed:

```bash
python -m src.main --run-id web-live-snapshot --export-web-snapshot
```

`--skip-openai` is supported. A production snapshot should prefer a grounded
interpretation when the key is configured.

Timing: after `QuantSummary` validation, after in-memory
`breadth_timeseries` / `trend_timeseries` exist, and after
`MarketInterpretation` is written (`available` or `unavailable`). The hook
runs after `market_report.md` so a failed presentation export cannot block
the accepted v1.0 report.

`--web-snapshot-dir` optionally redirects the snapshot (tests / local copies).
The default remains `web/public/data/`.

## Export failure behavior

A `WebExportError` does **not** invalidate the accepted v1.0 run:

- `outputs/<run_id>/` artifacts remain
- the exporter does not delete those files
- a warning is logged (`web snapshot export failed: ...`)
- the process exit becomes PARTIAL because of that warning
- any previous `web/public/data/` snapshot is left unchanged if the atomic
  write fails

`--export-web-snapshot` works with `--skip-openai` without changing skip
semantics.

## Purpose

Give the frontend one coherent, type-stable snapshot:

- latest quantitative facts (`quant_summary.json`)
- grounded AI interpretation (`market_summary.json`)
- historical series for charts (`breadth_timeseries.json`, `trend_timeseries.json`)
- a manifest that identifies the snapshot

## Manifest (`snapshot_manifest.json`)

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Web snapshot schema (`1.0.0`) |
| `run_id` | string | Same `run_id` as every artifact |
| `as_of_date` | `YYYY-MM-DD` | Snapshot as-of date |
| `generated_at` | ISO 8601 | Quant run timestamp |
| `quant_status` | `success` \| `partial` \| `failure` | From `QuantSummary.status` |
| `interpretation_status` | `available` \| `unavailable` | From `MarketInterpretation.status` |
| `artifacts` | object | Filenames for the four data files |

```json
{
  "schema_version": "1.0.0",
  "run_id": "fixed-run",
  "as_of_date": "2023-12-29",
  "generated_at": "2024-01-02T12:00:00Z",
  "quant_status": "success",
  "interpretation_status": "available",
  "artifacts": {
    "quant_summary": "quant_summary.json",
    "market_summary": "market_summary.json",
    "breadth_timeseries": "breadth_timeseries.json",
    "trend_timeseries": "trend_timeseries.json"
  }
}
```

## `quant_summary.json`

Copied from the validated v1.0 `QuantSummary` using the same serializer as
`outputs/<run_id>/quant_summary.json`. No web-specific quantitative schema.
Sector regressions remain in `sector_regressions`.

## `market_summary.json`

Copied from the validated v1.0 `MarketInterpretation`. Prose, evidence, status,
and disclaimer are unchanged.

## `breadth_timeseries.json`

Serialized from the accepted Phase 3 breadth DataFrame. Fields in each
`series` row:

- `date`
- `pct_above_50dma`
- `pct_above_200dma`
- `advancers`
- `decliners`
- `advance_decline_ratio`
- `net_advances`
- `breadth_momentum_20d`

Unavailable numeric values are JSON `null`. Dates are `YYYY-MM-DD`.

## `trend_timeseries.json`

Serialized from the accepted Phase 4 trend DataFrame. Fields in each `series`
row:

- `date`
- `adjusted_close`
- `sma_20`
- `sma_50`
- `sma_200`
- `trend_regime`

Early SMA values may be `null`. `trend_regime` is the stored enum, not a
reclassification.

## Null handling and JSON safety

- `NaN` → `null`
- `Infinity` is rejected
- Dates: `YYYY-MM-DD`
- Timestamps: ISO 8601

## Run / as-of consistency

Export fails unless:

- `quant_summary.run_id == market_summary.run_id`
- `quant_summary.as_of_date == market_summary.as_of_date`
- latest breadth date equals the snapshot `as_of_date`
- latest trend date equals the snapshot `as_of_date`

Do not mix artifacts from different runs.

## Existing v1.0 runs

Accepted run directories persist `quant_summary.json` and
`market_summary.json`, but not the in-memory breadth/trend DataFrames (only
PNGs). A complete web snapshot therefore requires calling
`export_web_snapshot(...)` during a future run, while those frames are still
in memory. Do not rebuild the series by calling breadth or trend formulas
inside the exporter.

## Frontend rule

TypeScript should model these files as explicit interfaces. The dashboard must
not calculate indicators. Display formatting (percent decimals, humanized
labels) is presentation-only.
