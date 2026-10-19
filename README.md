# KRATOS Stock Intelligence — evidence-first research

[Open the public dashboard](https://samin110597-create.github.io/kratos-stock-intelligence/)

An upgrade to the existing KRATOS project, separate from Q-State. The objective is
reliable observations and measurable research, not a claimed guaranteed trading edge.
No Vercel, brokerage automation, invented prices or calibrated confidence gauges.

## Use it

1. Open the dashboard and choose a published symbol.
2. Read the **minute price** and **completed daily close** separately. Check the
   timestamp, market status and source warnings.
3. Open **Technicals** to choose 15M, 1H, 4H, 1D or 1W candles and inspect FVG patterns.
4. Use **Fundamentals** for available provider facts and **Forecast & Plan** for
   explicitly illustrative scenarios and reference levels.
5. Open **Accuracy** to inspect frozen observations and separate outcomes. There
   is no proven trading accuracy yet. Institutional and news tabs disclose gaps.

**The current public site is snapshot mode.** The Python API is implemented, but
an external backend is not automatically created by publishing GitHub Pages. A
symbol outside published coverage needs the Python service below. No fake response
or watchlist substitution is used. The default published list includes a TSX example.

## What changed in v0.2

- NYSE/TSX exchange holidays, half-days and DST; closed 15M/1H/4H/1D/1W signals.
- Flat-price RSI = 50, missing warmup preserved, strict OHLCV/timestamp validation.
- Source-aware data, partial-failure warnings, bounded cache/retries/health status.
- Latest reported minute price kept separate from daily price references.
- Causal pivots, failed-range breaks, FVG age/touches/penetration/invalidation and
  explicitly labeled volume/VWAP proxies. No institutional-order inference.
- Append-only forecast/outcome events, hashes, exact maturity, revision checks,
  replayable exports. Legacy records remain archived and separately counted.
- Read-only any-ticker FastAPI service, input validation, rate limits and health.
- Real-data walk-forward experimental baselines; no model is promoted without
  additional independent validation. The initial NVDA experiment is available
  at [research.json](site/data/research.json) after a successful publishing run.

See [audit and remaining gaps](docs/AUDIT.md) and [data/hosting assessment](docs/DATA_SOURCES.md).

## Run on Windows

Install Python 3.11 or 3.12 and double-click `start_windows.bat`. This preserves the
existing Gradio app at http://127.0.0.1:7860. Leave that window running.

For the new dashboard and JSON API instead:

```bash
python -m pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:7860. Any supported US or TSX symbol (`NVDA`, `RY.TO`, `TSX:RY`)
can be requested, subject to vendor coverage and sufficient history. Provider
requests can take up to a few minutes; errors never become simulated data.

## Backend deployment

The Dockerfile runs `server.py` on port 7860. Use an explicitly authorized host;
verify current cost and data-display rights first. No paid service is auto-enabled.
For an eligible Hugging Face Docker Space, use `SPACE_README.md` as its README and
sync this repository. The current tool connection could not write to that account.

Environment:

- `PORT=7860`; `KRATOS_BIND=0.0.0.0` inside a container (local default is loopback).
- `KRATOS_ALLOWED_ORIGINS=https://samin110597-create.github.io` (comma-separated).
- `KRATOS_DB_DIR` for the Gradio local audit store; must point to persistent storage
  if forward history is to survive restarts. Public API writes are disabled.

After a real backend is deployed, set `site/config.json` `api_url` to its HTTPS
origin. Keep `same_origin_api=false` on Pages. The Python-hosted dashboard detects
its own API automatically; never put credentials in this configuration.

Endpoints:
- `GET /api/health`
- `GET /api/analyze?symbol=RY.TO`
- `GET /api/docs`

## Tests and publishing

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check site/app.js
python -m scripts.publish_snapshot
```

Unit fixtures are artificial and are confined to tests; they never become quotes.
Publishing uses real provider data, preserves explicit failed-refresh states, and
keeps prior forecast events immutable. GitHub Actions builds Pages after passing
Python tests. Scheduled builds are hourly and exchange-calendar gated. Browser
refresh is 15 minutes, never every 30 seconds. Neither is a live-data guarantee.

## Honest limits

Yahoo is the only operational data adapter. No licensed second source, verified
order flow, licensed options, filings/news engine, bank valuation, ETF holdings analysis,
portfolio sizing or notifications is implemented. Short-history IPOs fail closed.
The historical experiment uses revised single-symbol data, not a point-in-time
survivor-aware universe or net-of-cost trading simulation. No Strict/Adaptive grade,
BUY signal or confidence percentage has established positive expectancy.

This uses a deterministic orchestrator; it does not install the upstream Microsoft
Kratos Agent. See [integration notes](KRATOS_INTEGRATION.md). MIT license.

## Preserved personal options research

The existing **Options map · experimental** tab in the Windows/Gradio app remains
available. It computes assumption-based GEX/VEX/DEX/Charm scenarios from Yahoo
chains for personal research. These are not verified dealer positions or a live
options-flow feed; no options-book values are published on Pages or the public API.
See [the Free Research Lab guide](KRATOS_FREE_RESEARCH_LAB.md). The earlier daily
sweep/breakout and FVG research remains available alongside the new multi-timeframe
pattern diagnostics. No TerraShade code or private APIs are copied.
