# Public free analysis delivery

Visitors can start analysis without login or an owner password. The product
does not add accounts, a report history, or a globally advertised latest
report.

The Python quantitative engine remains frozen. New computation still runs in
GitHub Actions. Most visitors reuse the same immutable daily bundle.

## Product model

Anonymous visitor → Start Analysis → reuse today's accepted analysis if
valid, otherwise queue one real pipeline run → `/r/<opaque_token>` → View
Report / Download PDF.

`POST /api/run-analysis` is public. It does not accept or require
`RUN_ANALYSIS_SECRET`.

## Identities

- `run_id` / `analysis_id` — computation identity. Reuse keeps the original.
- `access_token` — visitor capability. New token per visitor, even on reuse.

The browser uses `/r/<access_token>`. `run_id` cannot load a report.

## Storage layout

Private Vercel Blob:

```
analysis/<run_id>/manifest.json
analysis/<run_id>/quant_summary.json
analysis/<run_id>/market_summary.json
analysis/<run_id>/breadth_timeseries.json
analysis/<run_id>/trend_timeseries.json
analysis/<run_id>/market_report.pdf

access/<access_token>.json
  → analysis_id, source_run_id, created_at, expires_at, reused

control/active_run.json
control/daily_quota.json
control/reusable_daily.json
control/cooldowns/<hashed_client>.json
```

Completed analysis objects are immutable. Aliases only reference them.

There is no bucket listing or public catalog.

## Daily reuse

`control/reusable_daily.json` stores `as_of_date`, `source_run_id`,
`analysis_id`, `generated_at`, and `status`.

Reuse requires:

- pointer status `success` or `partial`
- matching immutable analysis manifest
- stored pipeline `as_of_date` that is still the latest expected completed
  NYSE session

Report access TTL is **not** the freshness rule. A bundle can remain
downloadable for 7 days after it is no longer reusable for new visitors.

Latest expected completed session is computed in `America/New_York`:

- weekdays after 16:00 ET on a regular NYSE session → that date
- before the close, weekends, and full NYSE holidays → previous session

The Python pipeline remains the authority on the actual `as_of_date`. The web
check only decides reuse vs one new computation and never writes a date into
artifacts.

## Public request flow

1. If reusable daily analysis exists → mint a new alias → `reused: true`
2. Else if a computation is active → mint an alias to that `run_id` → poll
3. Else apply 15-minute client cooldown (hashed IP/header)
4. Else apply global quota: 3 new pipeline executions per UTC day
5. Else create `run_id` + alias, write queued analysis manifest, dispatch Actions

## Policy defaults

Server-only, never `NEXT_PUBLIC`:

| Variable | Default |
| --- | --- |
| `PUBLIC_RUN_COOLDOWN_SECONDS` | `900` |
| `PUBLIC_RUN_DAILY_QUOTA` | `3` |
| `REPORT_ACCESS_TTL_SECONDS` | `604800` (report/alias retention only) |
| `ANALYSIS_SESSION_COMPLETE_HOUR_ET` | `16` (freshness only) |
| `CLIENT_HASH_SALT` | optional extra hash salt |

Quota counts **new pipeline executions**, not visitors. Reuse and join-active
do not consume quota or cooldown.

## Abuse controls

- hashed per-client cooldown for expensive new runs
- global daily new-run quota
- one active new computation
- daily-result reuse

CAPTCHA/Turnstile is a future upgrade, not enabled now.

Raw IP addresses are hashed before storage and are not logged.

## Cost control

Many visitors do not imply many OpenAI calls. A typical day is one qualifying
pipeline, then reuse of the immutable bundle.

## Retention

Access aliases expire after 7 days (`expires_at`). Status/PDF/report then 404
for that token.

The underlying daily bundle is kept at least as long as the reuse TTL so
same-day reuse and remaining aliases still resolve. Cleanup must delete
aliases before or with the bundle they reference. Downloaded PDFs are the
durable copy.

## Admin escape hatch

`POST /api/admin/refresh-analysis` with `RUN_ANALYSIS_SECRET` can force a new
pipeline (skips reuse, cooldown, and quota). It is not shown in public UI and
is not required for public use.

## GitHub Actions

New computation only. Inputs remain `run_id` and `access_token`. Publish writes
`analysis/<run_id>/` plus the triggering alias and `control/reusable_daily.json`.
`--export-web-snapshot` is not used.

## Static snapshot

`/report` remains a labeled sample from `web/public/data/`.
