# KRATOS Stock Intelligence — Independent MVP

**A real, testable baseline, not a proven trading system.** Analyze a ticker using fetched historical/near-current OHLCV and fundamentals, with an explainable technical rule engine and an immutable 5/20-session forecast ledger. This is a completely **separate repo** from Q-State and contains **no Vercel, Azure or brokerage execution**.

> Important distinction: This code is **inspired by the original [Kratos Agent's](https://github.com/aiappsgbb/kratos-agent) "one agent, N skills" design**, but does **not bundle or claim to run** Microsoft's Copilot SDK, Azure Foundry, or the upstream agent. Please read [KRATOS_INTEGRATION.md](KRATOS_INTEGRATION.md) before asking Astra to integrate the upstream agent.

## Free-data Smart Money Research Lab (v0.2 experimental)

- **Public daily price structure:** The Technicals tab now shows completed-bar sweep/reclaim observations, prior 20-bar breakout boundaries, confirmed swing directions and still-open FVG price patterns. No unvalidated 90% predictions or asserted institutional orders.
- **Personal-use options map:** The Gradio app (`python app.py` or `start_windows.bat`) has an **Options map · experimental** tab. Enter a US optionable ticker and click **Fetch options positioning for ticker**. It calculates Black-Scholes GEX/VEX/DEX/Charm sensitivities using up to three available Yahoo option expiries, showing gross concentration, call/put concentrations, modeled gamma flip, and data limitations.
- **No paid API required.** The options data can be stale, throttled, missing, and is subject to Yahoo personal-use/redistribution restrictions. The public GitHub Pages site does **not** republish the new options-book figures.
- The dealer-position sign is an ASSUMPTION, not proven institutional positioning or live trade flow.
- **30 automated tests** were passing in GitHub Actions when v0.2 was validated; future changes must rerun CI.

Read [KRATOS_FREE_RESEARCH_LAB.md](KRATOS_FREE_RESEARCH_LAB.md) for the complete methodology, personal usage, data constraints and next steps. TerraShade public concepts were referenced independently; no code, private APIs or proprietary site assets were copied.

## What works in v0.1

- Gradio website, any valid Yahoo symbol (`NVDA`, `CIFR`, `RY.TO`, `BRK-B`, etc. subject to provider coverage).
- Queries real Yahoo Finance market data through `yfinance`; never substitutes synthetic price series when it fails. Uses 3y daily, 60d hourly, 5d 1-minute data. Provider may delay, throttle or block.
- Technicals: EMA20/50/200, Wilder-style RSI14, ATR14, volume ratio, 1H/4H/1D/1W rule-based trend, support/resistance and 52-week high/low. Daily, hourly, weekly *unfinished* bars are excluded conservatively. Intraday 4H aggregation is an approximation; no exchange holiday calendar.
- BUY SETUP / WAIT / AVOID-long classification with explicit filters. **BUY SETUP never appears if the minute source timestamp is older than 15 minutes during estimated regular hours.** A recent timestamp is **not proof of licensed real-time data**.
- Fundamentals: available provider fields, and *illustrative* forward-EPS × fixed-P/E sensitivity scenarios only when sensible. These are not intrinsic value estimates.
- Directional rule hypothesis and 5/20-session ATR-based sensitivity bands, **not calibrated forecast probabilities**.
- Immutable forecasts logged **before** future outcomes to SQLite. Evaluation uses 5th/20th subsequently completed daily bar, with unresolved/open and evaluated status and observed direction accuracy. No fake backtested wins.
- Unit tests and CI workflow. Secret-free code; local installation.

## Windows — easiest

1. Install **Python 3.11 or 3.12** from https://www.python.org/downloads/ (tick **Add Python to PATH**).
2. Download the project ZIP and extract the whole folder.
3. Double-click `start_windows.bat`. The first run installs packages (requires internet).
4. Open **http://127.0.0.1:7860** in your browser.
5. Enter any ticker and click **Analyze**. Inspect the Decision/Technicals/Fundamentals/Projection tabs.
6. To measure performance, go to **Accuracy audit → Record this forecast**. On later days, **Check completed outcomes**, or refresh the audit.

The app must be running on your computer to access it locally. Close its terminal to stop it.

## Mac / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

## Run tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Unit tests use clearly labeled artificial fixtures **only inside the tests**; the website never surfaces fixture prices.

## GitHub status and hosting

The source repository is **[samin110597-create/kratos-stock-intelligence](https://github.com/samin110597-create/kratos-stock-intelligence)** and is intentionally **public** with owner approval. **A public repository is not a deployed website**. GitHub Actions runs checks on commits; run the app locally using the instructions above or deploy it to a Gradio-capable Python host. GitHub Pages alone cannot run this Python backend. Never commit credentials, forecast databases, or private holdings.

## Optional private hosting (Hugging Face)

You can create a private Gradio Space and upload this repository, with `SPACE_README.md` as the Space README. Set `KRATOS_DB_DIR` to persistent storage **only if available**. **Free Spaces may have ephemeral disk**; forecast records can disappear after restarts. Never treat ephemeral storage as a trustworthy accuracy ledger. For production, migrate forecasts to a persistent private database and add login/authentication before sharing.

## Data and reliability limitations

- **Not financial advice / not proven accurate.** Rule-based baseline only. No ML model, no calibrated probability, no intrinsic value engine, no news/filings, options flow, dark-pool data, order blocks/FVGs or smart-money verification. These must be built and validated, not invented.
- US/Canadian regular-market hours are approximated as weekdays 9:30–16:00 Toronto time; exchange holidays, global venues, halts, split errors and pre/post-market trading aren't supported. Currency follows upstream metadata.
- `yfinance` is unofficial with no freshness or reliability SLA; during failure, the UI prints an error and records nothing. Daily volume on incomplete sessions is excluded from signals.
- **Provisional buy setup is a rule filter, not a signal with established positive expectancy.** Test after costs and measure over hundreds of untouched forecasts across different market conditions before using financially.
- sqlite is local only; do not deploy across workers without a durable transaction-safe database. No automated live orders or notifications.
- Last bar date/time and data-source timestamps are visible; data-freshness reports are conservative, and market session detection is only approximate.

## Files

| File | Purpose |
|---|---|
| `app.py` | Gradio UI, interactive analysis, charts, ledger controls |
| `kratos/data.py` | Verified source retrieval and freshness checks |
| `kratos/technicals.py` | Closed-bar indicators and multi-timeframe trend |
| `kratos/decision.py` | Explainable conditional trading rules |
| `kratos/fundamentals.py` | Provider fundamentals + cautious sensitivity analysis |
| `kratos/audit.py` | SQLite append-only forecast ledger + outcomes |
| `kratos/engine.py` | One orchestrator coordinating separate skills |
| `tests/` | Quality gates, including no-lookahead tests |
| `ASTRA_NEXT.md` | Specific instructions to improve and validate the baseline |

## License

MIT for original code in this project. Referenced upstream libraries and frameworks have separate licenses; their source code is NOT redistributed here.
