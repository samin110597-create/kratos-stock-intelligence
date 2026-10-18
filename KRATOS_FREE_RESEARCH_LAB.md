# KRATOS Free-Data Institutional Research Lab

## Status: v0.2 experimental, not a verified institutional trading system

This repository now includes two independent open-math research features:

1. \`kratos/structure.py\`: causal market-structure checks on finalized OHLCV bars; labels sell-side/buy-side sweeps, closed-bar breakouts, confirmed pivots, and still-open 3-bar FVG price-pattern candidates.
2. \`kratos/options_research.py\` + \`kratos/options_ui.py\`: option-chain sensitivity estimates (GEX, VEX, DEX and Charm) under transparent, **assumed** positioning conventions, displayed on-demand in the local Gradio application.

These are independently coded public-methodology implementations, **not** copied from TerraShade or an endorsement by it. The public TerraShade guide was consulted for *conceptual feature comparisons*; no private server APIs, code, proprietary artwork, credentials or paid datasets have been extracted.

### Why a free-data system cannot know "where smart money is buying"

- Option open interest **does not identify the sign of actual dealer holdings**. Scenario gamma/Vanna/Charm are not guaranteed dealer flows. Different assumptions can reverse the interpretation.
- Yahoo Finance/yfinance can be delayed, wrong, rate-limited or unavailable. Its data are intended for personal research; Yahoo expressly restricts redistribution. **Do not put its raw/derived options-book data onto a public website without adequate redistribution rights.**
- 13F institutional disclosures are backward looking, typically quarterly; Form 4 is transaction reporting; FINRA ATS/OTC data have reporting lag. None represent a complete live dark-pool order book.
- An FVG, order-block candidate, liquidation wick or high relative volume is **not proof** of an institution's orders.
- Zero-gamma is not a universal exact strike. It depends on contract completeness, assumed positions, IV and interest/dividend assumptions.

### How to use what is already built — Windows

1. Open the KRATOS repository and select Code → Download ZIP.
2. Extract the directory and double-click \`start_windows.bat\`; Python 3.11/3.12 is required.
3. Open \`http://127.0.0.1:7860\` on the Windows computer.
4. Enter a US optionable ticker, e.g. \`SPY\`, \`QQQ\`, \`NVDA\`.
5. Choose **Options map · experimental** → **Fetch options positioning for ticker**.
6. Inspect strike concentration, **assumption-based** gamma flip and net GEX, source timestamp, number of contracts, missing data and warnings.
7. In **Technicals**, review 20-bar closed-bar range sweeps, recent swing direction, and unfilled FVG candidate zones.

If a provider refuses option chains, the app explicitly shows **Options data unavailable** rather than fabricating values.

**Public GitHub Pages is a static read-only snapshot dashboard, not this on-demand Python app.** Options chain results are not auto-published to Pages.

### Existing free API accounts (connect safely in a future backend revision)

The user previously configured some free market/research APIs in other repositories. **GitHub Secrets are normally repository-scoped; never assume they were automatically copied into this new repository.** Their values must never be requested in chat, copied into code or emitted into browser JavaScript.

Recommended adapter priorities and verification obligations:

- **SEC EDGAR (no key):** companyfacts, submissions, prospectuses, 8-K and Form 4. Use official endpoint, descriptive User-Agent, publication timestamps, rate limits.
- **FRED with API key:** yields, policy rates, inflation, credit spreads and recession data. Research point-in-time economic vintages with ALFRED. Do not assign macro publications to dates before their public release.
- **Financial Modeling Prep free tier (if permitted):** basic financial fundamentals and limited quote endpoints. Confirm 2026 endpoint availability, limits and data licensing.
- **Finnhub free tier (if permitted):** company profile, earnings calendar, basic fundamentals and news. Confirm permissions, supported tickers, latency and daily limits.
- **Massive/Polygon free plans (if permitted):** equities end-of-day and limited options reference/history; 5 requests/minute appears in current public pricing. **Free is not licensed real-time streaming; individual plans may not permit public redistribution.**
- **Alpha Vantage (if permitted):** price/fundamental/macro fallback; respect severe free-tier quotas and release timestamps.
- **Yahoo Finance:** only personal research fallback, subject to Terms, **never treat fetch time as a licensed live exchange quote**.

Provider arbitration: a newer **source-reported market timestamp** wins only after validation. Never silently substitute a stale last daily close for a current quote. Keep strict rate limiting, provenance and missing-data behavior. API access to a provider does not equal ownership or public data redistribution rights.

### The next scientific validation step

Build a historic research dataset with immutable point-in-time feature values. For each known as-of bar, compute the observed market-structure and options features using **only information available at that date**. Measure whether a sweep, FVG retest, wall proximity, or assumed gamma regime affects subsequent 1h/4h/1d/5d probabilities compared with transparent baseline rules.

Use chronological walk-forward training, purged splits for overlapping labels, realistic execution costs and long/short or no-trade classifiers. Calibrate all probabilities. Never assign A/A+ or a "90% bounce probability" without a sufficient out-of-sample sample, and store all live forward predictions before outcomes.

### Immediate platform constraints

- The public Pages site supports scheduled coverage rather than every ticker on demand.
- Yfinance may fail for options, unsupported symbols or weekends; EOD OI is not intraday positioning.
- The current options model samples up to three earliest available expiries (not full market coverage) using unadjusted daily close; real bid/ask timestamps may be unavailable.
- No real dealer-book or options trade-flow feed. Black-Scholes sensitivities approximate American-style contracts.
- The rule-based model's existing 5-/20-session forecast ledger is not evidence of a profitable trading edge.
- No live trade execution, notifications, or validated bounce/sell-through probabilities.

**If results are missing, state UNKNOWN.** Adding more gauges never makes a system institutional-grade by itself.
