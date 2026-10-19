# Source and hosting assessment — checked 2026-10-18

Only **Yahoo via yfinance** is connected in this release. No vendor subscription
or entitlement was purchased, and no premium-feed benchmark is claimed. Runtime
latency/health is observable at `/api/health`; a recent response does not establish
trade freshness. Yahoo has no asserted freshness SLA or public redistribution grant.

| Source | Current role / verified limitation | Integration status |
|---|---|---|
| Yahoo/yfinance | Daily, hourly, 15-minute and minute histories; metadata. Unofficial, revision-prone; entitlement and event delay unknown | Active fallback-quality source, not institutional live feed |
| Massive/Polygon | Pricing page inspected, but plan detail not reliably extractable. US consolidated feed/delay/history/public display must be verified for the actual account | Not connected; no price/entitlement claim |
| FMP | Official pricing page describes 250 calls/day Basic; higher tiers include Canada/intraday. Display or redistribution requires a specific agreement. Page lists Premium $49/month and Ultimate $99/month billed annually; plan terms must be rechecked before purchase | Not connected; no licensed display agreement verified |
| Alpha Vantage | Official support states 25 requests/day standard free access (special verified-project provisions exist); US real-time and 15-minute-delayed feeds are premium | Not connected; no assumed free intraday entitlement |
| Finnhub | Pricing page could not be read in this environment; account entitlements, exchange coverage and display rights unverified | Not connected; do not assume free TSX/history/options |
| SEC EDGAR | Public submissions/XBRL JSON APIs without API keys; filing/acceptance dates matter; no browser CORS | Not integrated. Requires responsible client identity/rate controls and as-of mapping |
| FRED/ALFRED | Official API documentation inspected. Macro vintages are needed to avoid using revised values in past forecasts | Not integrated; no macro-aware trading claim |
| FINRA ATS/OTC | Public transparency source; reporting periods and publication delays must remain attached to observations | Not integrated; not live dark-pool prints or short interest |
| Cboe/OPRA | No licensed contract verified, and no options-print/dealer-position access available | Unavailable, not modeled |
| Canadian filings | No SEDAR+ ingestion implemented; TSX price support is not Canadian filing coverage | Unavailable |

Official references:
- https://massive.com/pricing
- https://site.financialmodelingprep.com/developer/docs/pricing
- https://www.alphavantage.co/support/
- https://finnhub.io/pricing
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://fred.stlouisfed.org/docs/api/fred/
- https://www.finra.org/filing-reporting/otc-transparency
- https://pandas-market-calendars.readthedocs.io/en/latest/usage.html

## Hosting

- GitHub Pages serves static snapshots. Python cannot execute there. Best-effort
  scheduled builds do not guarantee an hourly or 15-minute delivery deadline.
- https://huggingface.co/docs/hub/spaces-overview currently says ordinary Gradio
  and Docker Space creation requires Pro (personal) or an eligible organization
  plan; free accounts in good standing have a limited ZeroGPU Gradio exception.
  CPU Basic has no hourly charge, but that does not imply creation is available
  to every free account. Default disk is nonpersistent; sleeping compute has no
  always-on guarantee. No paid plan was enabled for this task.
- A production backend needs write-authorized hosting, outbound market-data access,
  appropriate licensing, persistent event storage, uptime monitoring and backups.
  The included Docker service works without brokerage credentials or GPU compute.
