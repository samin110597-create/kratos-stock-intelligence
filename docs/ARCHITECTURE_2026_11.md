# Authorized architecture and verified constraints — November 12, 2026

GitHub is canonical. Pages serves the dashboard. Python handles calculations.
Only Hugging Face Spaces is authorized as a future backend host. Render and Vercel
are not used by this deployment; the previous Render URL and deployment file were removed.

## Hosting verification

Connected Hugging Face identity: Smit1105, non-Pro personal account. OAuth scopes
include read-repos but not repository write. The public account Space listing was
empty. Private/unlisted reusable Spaces could not be conclusively inventoried with
the available connector. No paid service was activated.

Current official documentation says Docker/Gradio compute Space creation requires
Pro for individuals. CPU Basic has no hourly hardware charge, but that does not
make creating a Docker Space subscription-free:
https://huggingface.co/docs/hub/spaces-overview

Therefore no eligible free Docker backend was deployed. GitHub Pages remains a
functional **dated research archive**, not an any-ticker Python backend. GitHub
Actions cannot safely serve anonymous arbitrary frontend requests without an
additional authenticated request service. No credential is embedded to bypass this.

## Five upstream modules

- Qlib: genuine pyqlib 0.9.7 DatasetH / LinearModel ridge, historical expanding-window
  out-of-sample tests. One-session return target, one-row embargo, frozen parameters,
  comparison with no-change. Small revised-data samples; no production model claim.
- VectorBT: genuine vectorbt 0.28.2 Portfolio.from_signals, fixed 10/30-day MA rule,
  signal on completed close, fill next open, 10 bps fees plus 5 bps slippage per fill.
  OB/FVG/RSI/liquidity diagnostics remain custom Kratos calculations, separately labeled.
- OpenBB: not installed/integrated. Existing provider facts are preserved and labeled
  as Kratos. No statement pipeline or intrinsic-value estimate claimed.
- TradingAgents: not installed/integrated. No authenticated, cost-approved inference
  endpoint verified. Deterministic context is explicitly not an AI committee.
- QuantConnect LEAN: not installed/integrated. No compatible runtime/data bundle tested.

## Research and durability

Training and backtesting run offline, never in /api/analyze. The scheduled Actions
job uses only existing archived input, skipping unchanged input/code hashes. It does
not renew market-data timestamps or claim new data. Completed runs are stored under
site/data/framework-runs/<symbol>/<content hash>.json and versioned in Git. The index
contains source receipt time, last data session, input hash, framework version,
held-out predictions/outcomes and cost assumptions. These are retrospective research
records, not forecasts recorded before real-world outcomes. Existing forward forecast
ledger files are preserved; new on-demand forward recording remains unavailable.

## Backend readiness and recovery

The preexisting Python API accepts supported US/TSX symbols independently of snapshots.
The frontend retries transient backend failures twice, retains one ticker across tabs,
refreshes the backend every 15 minutes when configured, and rejects attaching an old
experiment to a newer analysis data version. Sensitive account routes remain protected.
Financial API credentials remain server/Actions secrets; no values are published.

Remaining live acceptance checks require an eligible backend: NVDA, GOOG, RY.TO and
an absent ticker such as AAPL must succeed against the deployed service. Local provider
probes or mocked route tests are not substitutes for that acceptance check.
