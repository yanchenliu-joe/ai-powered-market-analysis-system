# Acceptance evidence

Generated 2026-09-11. No API keys or secrets are included.

## Fixed Fixture Acceptance

- Date: 2026-09-11
- Run ID: `fixture-acceptance` (deterministic integration test)
- Command:

```bash
.venv/bin/python -m pytest tests/test_integration.py -q
.venv/bin/python -m src.main --fixture --skip-openai --run-id fixture-acceptance
```

- Test result: `tests/test_integration.py` passed, including a mocked-OpenAI full artifact run with exit SUCCESS (`0`) and a `--skip-openai` run with exit PARTIAL (`2`).
- Artifact checklist for the mocked success path:
  - `quant_summary.json`
  - `breadth_timeseries.png`
  - `spy_trend.png`
  - `sector_rate_beta.png`
  - `market_summary.json` (canonical interpretation fields populated)
  - `market_report.md`
- Internet: not used
- Real OpenAI: not used
- Final status: SUCCESS for mocked interpretation; PARTIAL for intentional skip

## Real Data Acceptance

- Execution date: 2026-09-11
- Command:

```bash
.venv/bin/python -m src.main --skip-openai --force-refresh --run-id real-acceptance-20260911 --log-level INFO
```

- Provider result: succeeded after Wikipedia User-Agent fetch; yfinance reported a transient SSL error for `QCOM` and missing prices for `HUM` (recorded as a data-quality warning).
- Run ID: `real-acceptance-20260911`
- Requested range: 2021-09-11 to 2026-09-11
- Actual as-of date: 2026-09-11
- Coverage:
  - Universe size: 503
  - Available equity tickers: 502
  - Latest 50DMA valid count: 502
  - Latest 200DMA valid count: 500
  - SPY observations: 1255
  - DGS10 usable observations: 1247
  - Sector ETFs: 11 available, 11 valid regressions, 0 insufficient
- Quantitative status: `success`
- OpenAI mode: `--skip-openai` (`market_summary.json` status `unavailable`, reason `skipped`)
- Artifact checklist:
  - `quant_summary.json`
  - `breadth_timeseries.png`
  - `spy_trend.png`
  - `sector_rate_beta.png`
  - `market_summary.json`
  - `market_report.md`
- Final CLI status: PARTIAL (`2`), as specified for intentional OpenAI skip
- Environment notes: live Wikipedia initially returned HTTP 403 without a User-Agent; production fetch now sends a User-Agent. Fixture caches are isolated under `data/raw/_fixture/`.

OpenAI success path was verified independently by mocked tests, not a paid live completion.

## Quality Gates

- pytest: 237 passed
- overall coverage: 91%
- breadth: 90%
- trend: 91%
- regression: 93%
- schemas: 90%
- quant_pipeline: 90%
- visualization: 92%
- interpretation: 100%
- reporting: 97%
- ruff: passed
- black: passed
