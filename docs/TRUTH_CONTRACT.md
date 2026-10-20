# KRATOS TRUTH CONTRACT v1

The site **does not have a validated predictive trading edge**. It must prefer an honest unknown over a convenient guess.

## Four evidence classes

| Class | Meaning | What must NOT be implied |
|---|---|---|
| `PROVIDER_REPORTED` | A named upstream vendor returned a price/fundamental field with traceable retrieval time. | Independently verified, licensed real-time, or sourced from original filings. |
| `CALCULATED` | A deterministic feature computed from the observed historical bars (e.g. RSI, ATR, swing high, FVG pattern). | Profitable, forward-predictive, or evidence of an actual institutional order. |
| `HYPOTHESIS` | A potential entry level, volatility-sensitivity band, trading scenario or direction model. | A forecast with calibrated probability or a trade recommendation. |
| `UNAVAILABLE` | Data is not reliably provided, such as dealer inventory or verified dark-pool orders. | Zero, neutral, not present, or evidence against a hypothesis. |

## Programmatic enforcement

- `kratos/truth.py::build_evidence_report` validates retrieval timestamp, provider identity, completed daily-bar reference, observed minute-bar timing, and decision grade.
- Attempts to publish a rule-engine BUY SETUP or unsupported confidence/real dealer position are rejected.
- The public publisher embeds `truth` in each ticker snapshot. If a ticker fails validation, it does not receive a newly validated record. Any old snapshot remains labeled **refresh_failed**.
- The public Dashboard displays an evidence-status panel with disclosed missing capabilities.
- `tests/test_truth.py` tests future timestamps, missing source identity, impossible daily-bar dates, invalid reference prices, unsupported probabilities and unverified BUY claims.
- The existing append-only forecast ledger evaluates forward outcomes without altering original predictions.

### What this check DOES NOT prove

A software validation gate **cannot** prove Yahoo/other upstream prices are true. There is no independent cross-vendor price check yet, no licensed live-feed entitlement, and no professional data quality audit. The truth contract is a *claim-control and consistency check*.

It cannot assert prediction accuracy without matured, non-retrofitted outcomes. Every model's sample count, methods, costs, statistical uncertainty and comparable benchmarks must be examined before supporting trading decisions.

### Data freshness rule

Treat **bar market timestamp** and **API retrieval timestamp** separately. A timestamp from an HTTP download does not turn an old daily close into a live quote. During open market hours, if no recent exchange bar can be verified, the engine remains research-only and cannot issue a live setup.

### Institutional / free options rule

Gamma, delta, charm, vanna and call/put wall estimates from available options-chain OI are mathematical sensitivities **under declared dealer-sign assumptions**. Actual dealer positions and hedging trades are unknown. An option chain may be delayed, incomplete, or missing legitimate strikes. No dealer-flow directional claim is allowed.

### What to implement next

1. Independent source cross-check with two actually available free data providers, including exchange, currency, as-of time and corporate actions reconciliation.
2. Point-in-time original SEC/SEDAR filings and source-linked catalyst timestamps; unknown if unavailable.
3. True walk-forward tests, with per-ticker market regime samples, target-before-stop outcomes, slippage/commissions and versioned model promotion.
4. Calibrated probabilities only after sufficient out-of-sample data; until then display **INSUFFICIENT VALIDATION**.
5. Durable monitoring for failed provider fetches, stale schedules, missing symbols and audit-storage corruption.

**Never fabricate success, institutional activity, probability, news, price, profit or validation.**
