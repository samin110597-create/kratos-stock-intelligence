# KRATOS integrity upgrade — 2026-10-18

Scope: the existing `samin110597-create/kratos-stock-intelligence` repository only.
No Q-State changes, brokerage execution, subscriptions, or Vercel services.

## Reproducible baseline

Base commit: `a4934734fdd6c64b9e54c8c81eded8f850c4eb58`.
Original tests: **16 passed** in an isolated checkout. Initial local import failed
because the execution environment uses SOCKS proxies and lacked `socksio`; installing
`httpx[socks]` resolved that environmental issue. It was not counted as a code defect.

The first 11 cases in `tests/test_integrity.py` were run on the original implementation:
**11 failed**. The same cases pass with the fixes. These were actual observed failures:

| Defect | Correction / regression test |
|---|---|
| Flat RSI returns 0; warmup masquerades as an indicator | Both zero → 50; warmup remains missing |
| Duplicate timestamps silently overwrite observations | Reject duplicates |
| Unordered timestamps silently reordered | Reject non-monotonic histories |
| Impossible OHLC values accepted | Positive finite values, high/low envelope, valid volume |
| Christmas treated as an open US market | NYSE calendar |
| Canadian Thanksgiving treated as TSX trading | TSX calendar distinct from US |
| Half-day daily bars wait until normal close | Actual scheduled early close |
| Future daily rows leak into analysis | Every row checked against its own close |
| Final 30-minute hourly bar waits a full hour | Cap bar end at session close |
| Good-Friday weekly close waits until Friday | Actual last session of that week |
| Missing aggregate volume becomes zero | Missing stays missing |

Additional checks cover incomplete/missing-component 4H buckets, DST, causal pivot
confirmation, ETFs, source failure, API rate limits, event immutability, corruption,
price revisions, exact outcome maturity, and walk-forward leakage. They were added
with the new modules; they are not claimed as before/after failures of old APIs.

## Important architectural repairs

- Session buckets start at 09:30 local exchange time. 4H consists of 09:30–13:30
  and 13:30–close, with shortened final/half-day buckets. All expected component
  bars must exist. Weekly bars require all scheduled daily sessions. These are
  explicit conventions, not universally standardized vendor candles.
- 15M/1H/4H/1D/1W signals use completed candles. A recent minute bar is separate
  observational price information, possibly developing, never mislabeled a close.
- OHLC requests use `auto_adjust=False`. Yahoo can still revise/split-normalize
  history. Corporate actions and large discontinuities are disclosed. Missing
  volume, quote currency, entitlement, provider-event time and delay stay unknown.
- Provider routing has explicit source priority, bounded caching, retries and
  health results. **Only the Yahoo adapter is operational**; no paid feed implied.
- A rule-filter pass no longer becomes a BUY recommendation without validation.
  Strict/Adaptive remain unvalidated with zero graded samples.
- Forecast creation time is after source retrieval, not the beginning of a batch.
- Forecasts and outcomes are separate SQLite events with update/delete rejection,
  canonical payloads, SHA-256 links and export/import integrity checks. Exact
  scheduled maturity prevents missing bars from silently moving the scoring date.
  Revised/missing reference history and reported splits block scoring.
- Public events are versioned in Git as `site/data/events.jsonl`. Old JSON ledger
  stays untouched and excluded from new results. Hashes detect alterations; they
  are not external notarization or protection against an administrator replacing
  an entire history. Local SQLite requires a persistent host and backups.
- Public API is read-only. It cannot write arbitrary user forecasts or reveal
  portfolios. Its request cache and throttle are per process; production horizontal
  scaling needs a shared limiter/cache and correctly configured trusted proxies.
- GitHub Pages artifacts can update without a snapshot-only Git commit every hour.
  Git persists new observations/outcomes, along with that run's snapshot. Scheduled
  runs are exchange-calendar gated. Schedules and unofficial data have no SLA.

## Research actually implemented

Descriptive confirmed pivots, HH/HL and LH/LL sequences, prior-range breakouts and
failed breaks, FVG boundaries/age/touch episodes/penetration/invalidation, volume
and typical-price VWAP proxies. These are OHLCV patterns, not observed institutional
orders. FVG hold/break probability is unavailable.

`kratos/research.py` benchmarks no-change, historical mean, momentum, mean reversion,
and fixed-alpha ridge on daily 5/20-session returns. Features are causal; training
labels end at least one horizon before the test origin. The last 120 available
sessions are the evaluation window. Evaluation origins are a horizon apart, but
features remain correlated. No tuning or model promotion uses test results.
`site/data/research.json`, when successfully generated, contains the real dataset
hash, date coverage, every prediction/actual, sample counts and baseline metrics.

This is a small **historical walk-forward experiment**, not an independent locked
multi-regime production validation, not a point-in-time survivor-aware universe,
not calibrated probabilities, and not after-cost trading performance. Neural
networks, calibrated grades and 15M/1H/4H predictive models are still unimplemented.
Forward observations stay separate from historical experiments.

## P0 / P1 scope and outstanding work

Core P0 bugs addressed; no claim of complete institutional-grade audit. P1 API and
frontend integration implemented and locally tested. The public Pages deployment
still needs a separately hosted backend for arbitrary on-demand symbols. A Docker
image definition and documented API are included. Hugging Face account `Smit1105`
was accessible read-only, without repository write scope; no local HF credential
was available. The account was not Pro. Current HF docs also impose plan conditions
on ordinary Docker/Gradio Space creation. No backend URL is claimed as deployed.

Still absent: licensed second-source data, cross-provider price reconciliation,
trade/quote order flow, options prints/GEX, filings-based statements, point-in-time
fundamentals, sector valuations, news/catalyst interpretation, macro regime data,
portfolio risk, verified corporate action normalization, calibrated zone models,
alerts, and robust independent predictive validation. IPOs with fewer than 65
completed daily bars return insufficient history. Supported calendars are US
regular-session equities and TSX/TSXV conventions; global symbols/crypto fail closed.

## Rollback / recovery

Revert a code commit through a new Git commit and let Pages rebuild; do not reset
or rewrite the public event file. Restore SQLite from a verified event export via
`kratos.audit.import_events`. Existing legacy SQLite `forecasts` tables are retained
but not migrated into scored v2 events. Keep a copy before any manual migration.

## Integration with subsequent work

Remote head `d1f22ae` added a personal-use options map and daily causal market
structure after the original audit began. These changes and their tests were
preserved during integration. `kratos/structure.py` retains that daily report;
`kratos/patterns.py` contains the new multi-timeframe lifecycle diagnostics.
Personal-use options scenarios are distinct from unavailable licensed options
prints or verified dealer holdings. They remain outside the public API/Pages feed.

## Predeployment concurrency finding

A resumption check detected two local publisher processes appending independently
based on an initially empty event file. Individual hashes were valid but the
combined chain forked. This was caught before publication. The exact original
50 event lines are retained in `site/data/predeployment-events.jsonl`, explicitly
unscored. None is relabeled a successful forward forecast. The canonical active
ledger starts empty and records fresh observations after this repair. Publishing
now holds a process-level file lock for the full read/compute/append transaction
and refuses to append if the original file changed. Scheduled jobs remain serialized.
