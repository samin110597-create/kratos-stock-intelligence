# For GPT-6 Astra High / Work — refine this existing repository

You are continuing a **working baseline**, not starting over. Work in the separate private GitHub repository `kratos-stock-intelligence`. Never modify Q-State. Read the existing source, run the test suite, fix problems first, and preserve deterministic testable semantics.

Priority 1 — DATA TRUTH:
- Replace sole unofficial yfinance dependency with configurable authenticated feeds and exchange calendars. Support US/TSX ticker mapping, timezone-aware corporate actions, point-in-time data, delayed-feed warnings and source provenance. Target ≤15-minute data when markets open, but never guarantee provider capability without verification. Reject stale/missing facts.
- Implement safe caching/rate limits, provider-fallback policy, data-quality unit/integration tests, monotonic bar timestamps, backpressure and error reporting.
- Authentication, encrypted secrets, persistent DB, migrations, audit backups; no Vercel, no public deployment without consent.

Priority 2 — TECHNICALS:
- Add true closed-bar 15m/1H/4H/1D/1W market structure (HH/HL/LH/LL, BOS/CHoCH, sweeps, failed breakouts, anchored VWAP), validated OB/FVG/IFVG freshness, retests, actual candle-anchored volume, volatility-aware levels, scenario invalidations.
- No lookahead/repaint: each output must be reproducible given a timestamp and as-of provider snapshot.

Priority 3 — FUNDAMENTALS + CATALYSTS:
- Filings/earnings financials, dilution, cash runway, debt, growth quality, revisions, sector-adjusted valuation with transparent uncertainty; bank-specific tangible book/ROTCE/credit/capital methods. Separate true intrinsic-value calculations from illustrative sensitivities.
- Company-specific real news and catalyst tagging, with links/time and immediate/medium-term interpretations; report unavailable institutional/options/dark-pool data honestly.

Priority 4 — FORECAST VALIDATION:
- Enforce frozen, pre-event forecasts and immutable inputs/features/models; add distinct Strict/Adaptive grades and evaluation by 15m/1h/4h/1d and 5/20 trading sessions. Track calibration, directional accuracy, precision/recall, MAE, trades including realistic fills/slippage/commissions, maximum drawdown and regime breakouts.
- Out-of-sample anchored walk-forward benchmarks vs naive direction/no-trade and buy/hold, purged/embargoed splitting; distinguish walk-forward simulations from real forward live outcomes. Never fit a confidence number without calibration.
- Add independent ML candidates only when they beat transparent baselines after costs; publish model cards and failure examples. Retraining must never rewrite archived predictions.

Priority 5 — USER EXPERIENCE:
- Improve Gradio UI or equivalent with clear BUY SETUP/WAIT/AVOID, data freshness, one-click any ticker, scenario forecast and risk levels, evidence links, easy-to-read trend table. Technical, Fundamental, Catalysts, and Accuracy as separate tabs.
- Build an actual private secure deployment using a free/low-cost platform where feasible; separately identify provider subscriptions or persistence costs. Verify the live URL, no Vercel.
- Test Windows setup and hosted deployment and provide plain-language usage instructions.

Kratos: examine `KRATOS_INTEGRATION.md`. Integrate actual `aiappsgbb/kratos-agent` only after auditing dependency/licensing/cost; prefer portable local MCP skills. Never falsely state the hosted upstream agent is already active.

**Definition of done:** source committed in separate private repo, tests pass, app accessible with permissions enforced, verified valid tickers and informative failures, persistent integrity-tested forecast ledger, measured *honest* out-of-sample results, sources/timestamps displayed. If something cannot be verified, say so precisely.
