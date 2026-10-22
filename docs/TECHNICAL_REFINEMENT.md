# Structural price plans — 2026-10-22

The former plan centered every entry on EMA20 and projected 1.5/2.5/4 times
risk regardless of observed price obstacles. The replacement `structure-plan-v1`
uses confirmed price swings, prior range boundaries and closed-bar triggers.
Fundamental calculations are unchanged.

- Each 15M/1H/4H/1D/1W frame explains rising/falling structure, range,
  recovery, breakout attempt, breakdown or rejected resistance. Missing frames
  remain unavailable. Moving-average context is labeled separately.
- Pivot levels require two confirming bars and must be known strictly before
  the decision bar. Prior 20-bar boundaries exclude the decision candle.
- Nearest observed floors/ceilings supply conditional paths. No fixed risk-multiple
  targets, ATR time envelopes, arrival dates or probability claims are generated.
- Long plans require a bullish support rejection or a later retest after a
  prior-bar breakout. Stops sit below the observed rejection low and support,
  buffered by 0.15 ATR. Entry bands bound chasing; a next-open gap outside them
  cancels the simulated entry. No overhead target means no qualified candidate.
- Candidate filters require 1.5R to the FIRST resistance after assumed 20bp
  costs, at-least-average prior-20-bar volume and no bearish daily/weekly conflict.
  A candidate remains WAIT until independently validated. AVOID concerns new
  long entries in falling/broken structure; it is not a short recommendation.
- Relative volume now compares with the prior 20 bars, excluding the signal bar.
- New forward records carry their plan version. Existing immutable events and
  historical decisions are preserved.

## Visible archived examples

`scripts/refine_archive.py` writes a separate `site/data/plans.json` for the saved tickers
from its already-published candles (at most 100 per timeframe). It makes no network
calls, preserves the original snapshots byte-for-byte, and never writes the forward event ledger.
The website labels these historical re-analyses and shows their source session date.
The personal backend uses up to 252 completed bars per frame, so its longer history
can yield different levels. Re-analysis is not evidence of a forecast made earlier.

## Validation and actual historical check

Regression fixtures check strictly prior pivot availability, future-prefix invariance,
invalid OHLC rejection, no immediate entry on a breakout attempt, breakdown avoidance,
observed target provenance, stops below rejection lows, missing intraday data and
prior-only volume. These test behavior, not trading profitability.

Ran `python -m scripts.evaluate_structure data/research-check/nvda-actual-history.csv`
on the previously retrieved NVDA series through 2026-10-20. The fixed evaluation
uses the final 504 daily bars, every fifth origin, a five-session holding cap,
next-open entry only inside the frozen band and 20bp round-trip costs. It produced
**zero qualifying candidates and zero trades**, so expectancy and win rate are
unavailable. No thresholds were relaxed after seeing that result. This sparse
single-series check does not establish an improvement in predictive accuracy.

These plans improve traceability and explanation. They still lack independent
live-forward validation, a point-in-time universe, verified execution prices and
historical intraday strategy tests. Public any-ticker hosting remains a separate
unresolved deployment dependency.
