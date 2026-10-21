# Free-data research upgrade — 2026-10-21

This extends the existing repository and preserves the newer truth-check module.
Q-State was not modified. No paid services are selected.

## Actual source boundaries

| Connector | Implemented request | Limits enforced locally | Scope |
|---|---|---|---|
| FMP | Stable company profile | 5/min, 250/rolling day | Basic advertises EOD/reference coverage; endpoint access checked per account |
| Finnhub | Timestamped stock quote | 30/min, 500/rolling day | Conservative application budget, not a promise of consolidated live coverage |
| FRED/ALFRED | Series observations, optional vintage date | 10/min, 100/rolling day | Date-level vintage; not intraday publication timestamps |
| Massive / Polygon | Previous daily aggregate, unadjusted | 5/min, 100/rolling day | Basic EOD, not a current quote |
| Alpha Vantage | Compact raw daily history | 5/min, 25/rolling day | Optional daily-only market-history adapter; no live/intraday guarantee |
| Alpaca | Indicative option snapshots, page token | 10/min, 100/rolling day | Modified indicative quotes and derivative trades delayed 15 minutes; no OI in snapshot API |
| Twelve Data | Daily time series diagnostic | 8/min, 800/rolling day | Basic internal non-display terms; not exposed as a dashboard source |
| OCC | Daily CSV report download | Explicit manual invocation only | HTTP 403 observed from this environment; no report or contract-level mapping claimed |
| Yahoo | Existing stock/options personal fallback | Existing bounded router/cache | Unofficial; not a licensed public feed |

The five account connectors are complementary. FRED observations cannot replace prices;
FMP profiles cannot replace OHLC; Massive previous-day bars cannot provide intraday charts.
No fallback silently upgrades a plan. No quote is synthesized when a source fails.

Credentials are read only from environment variables. The private connector endpoint returns
native payloads with retrieval timestamps, source timestamps where available, and limitations.
SQLite budgets/cache persist only when the host filesystem persists. Other apps using the
same account key consume quotas that this process cannot observe. The GitHub diagnostic makes
one request per configured provider and prints status only; it does not upload provider payloads.

`KRATOS_PROVIDER_ORDER=alpha_vantage,yahoo` explicitly selects the compact daily account feed
first, with Yahoo fallback if the account endpoint fails. The default remains the existing Yahoo
personal analyzer to preserve five-timeframe functionality. Daily-only coverage is clearly marked.
The other connectors are available through protected `/api/source/{provider}` and `/api/providers`.
They are not falsely presented as a merged, independently cross-checked price feed.

## Options and causal technical repairs

Two new regression tests fail before repair: shortened-session expiry and inconsistent put
position signs in DEX. Expiry uses the NYSE cash close as a conservative proxy, **not** a claim
about every contract's final exercise or settlement time. Adjusted/nonstandard multipliers are
rejected. GEX shows call-long/put-short, its inverse, all-long, all-short and balanced scenarios.
The personal options UI adds expiry/strike OI heatmaps and strike IV curves. OI changes require
two explicitly dated reports matching the same contract; last trade time is not OI publication time.
Alpaca raw indicative snapshots remain separate from OI and are never passed off as OPRA prints.

Multi-timeframe structure adds closed-bar crossings of previously confirmed pivots (BOS/CHoCH),
session-reset typical-price VWAP, prior-volume participation and existing failed breaks/sweeps.
FVG lifecycle touch counts stop at invalidation. These are causal descriptions, not calibrated edges.

## Target-before-stop research

`kratos/target_paths.py` defines a fixed long-only experiment: prior-close 1.5 ATR invalidation,
3 ATR target, next-open entry (cancel if the open is outside either barrier), 5/20-bar horizons.
Gap stops fill at the opening price; target gaps conservatively fill at the target. Same-bar hits
are excluded from probability calibration and treated as stop-first for modeled P&L.
The default round-trip cost assumption is 20 basis points and is configurable for sensitivity runs.

Non-overlapping candidate holding windows; expanding chronological training, a separate calibration
window, label purging plus a horizon embargo, and later test folds. Train-only scaling and fixed
logistic settings; historical-frequency baseline. Five-bin calibration uses shrinkage and no test
labels. Report Brier score, calibration bins, trade sample size, net wins/losses, net expectancy,
timeouts, ambiguous bars and modeled drawdown. Individual predictions retain split boundaries.
No future probability, BUY policy or model promotion is enabled by these historical tests.

Revised price history is not point-in-time history. There is no delisted universe or verified
historical news/financial/options feature archive. Sparse history returns insufficient validation.
The old frozen event archive and new historical research remain distinct.

## Hosting and publication

`render.yaml` specifies **plan: free**, the existing Python service, and a generated personal access
token. Render is not deployed until an authorized account connection is available. Free services
sleep; local storage is ephemeral, so this is not durable live-forward storage or a freshness SLA.
HF currently requires a paid plan to create Docker/Gradio compute Spaces; no paid plan was purchased.

Hosted personal endpoints fail closed without `KRATOS_ACCESS_TOKEN`. The same-origin dashboard
accepts this service token in a password field and holds it only in page memory. Do not enter a
provider API key in the website. The API supports Authorization headers and configured CORS origins.
The default local server remains bound to 127.0.0.1.

New Yahoo market-data publication on public Pages is paused, per the personal-use-only requirement.
The historical archive is preserved. The publisher now writes to ignored `data/personal` by default;
public Git does not receive new personal provider responses. Public refresh schedules were removed.
The private backend provides on-demand analysis and a manual historical-test button in Accuracy.

## Verified official references (read 2026-10-20/21)

- https://site.financialmodelingprep.com/developer/docs/pricing
- https://site.financialmodelingprep.com/insights/platform/what-to-do-after-your-first-successful-fmp-api-call
- https://finnhub.io/docs/api/quote
- https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- https://massive.com/docs/rest/stocks/aggregates/previous-day-bar
- https://massive.com/knowledge-base/article/how-quickly-can-i-access-massives-market-date
- https://www.alphavantage.co/support/
- https://docs.alpaca.markets/us/docs/historical-option-data
- https://docs.alpaca.markets/us/reference/optionchain
- https://www.theocc.com/market-data/market-data-reports/other-market-data-info/batch-processing/daily-open-interest
- https://twelvedata.com/pricing
- https://render.com/docs/free
- https://huggingface.co/docs/hub/spaces-overview

## Actual historical run

On 2026-10-21, retrieved 2,512 NVDA daily bars through the completed 2026-10-20 session,
using the unchanged 10-year Yahoo query and the fixed experimental settings. Five-bar
walk-forward testing produced 359 scored observations: frequency baseline Brier 0.094976,
fixed logistic 0.094438, calibrated logistic 0.095674 (lower is better). Calibration made
this experiment worse than its baseline. No model crossed the predefined 0.60 trade
threshold, so net trading expectancy is **unavailable**, not zero or proven profitable.
Twenty-bar testing had no eligible test folds under the minimum training/calibration
requirements; those requirements were not relaxed to manufacture a result.

Reproduce privately: `python -m scripts.research_paths NVDA`. Results and source CSV are
written under ignored `data/research-check`. Revised history can change future reruns.
These are historical observations, not point-in-time or independent live-forward validation.

Dataset SHA-256 for this run: `2e3f326ee5b2f5a72ef268dbe0b6a0694086ba3e300ab35e6f1b4397a99e946e`.
