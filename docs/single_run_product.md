# Single-run product model

The product is a public free analysis. It does not offer login, user accounts,
or a shared report archive.

A visitor views a generated report for one execution and keeps a durable copy
by downloading `market_report.pdf`. No personal history is promised because
there is no identity layer to own that history.

Live owner-triggered execution is documented in `docs/live_run_delivery.md`.
The live report URL is `/r/<access_token>`, not `/report?run=<run_id>`.

## Sample development snapshot

`/report` renders the static snapshot in `web/public/data/` and is labeled as a
sample/development report. Live runs must not overwrite that directory.

## PDF artifact

- Filename: `market_report.pdf`
- Pipeline location: `outputs/<run_id>/market_report.pdf`
- Sample download path: `/data/market_report.pdf`
- Live download path: `/api/runs/<access_token>/pdf`
- Timing: after `market_report.md`, from the same validated objects
- Charts: included when `breadth_timeseries.png`, `spy_trend.png`, and
  `sector_rate_beta.png` already exist in the run directory
- Failure: PDF failure warns and does not delete accepted JSON/Markdown/PNG
  artifacts

The PDF renderer copies already-validated quantitative and interpretation
fields. It does not recompute breadth, trend, regressions, or AI text.
