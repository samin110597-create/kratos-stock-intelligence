# Hosted personal analysis

Render service: `kratos-personal-research` in the confirmed My Workspace.
Runtime is Python on Render's free web-service plan in Ohio. No paid database,
disk, worker or scheduled task was created. This service was created directly;
`render.yaml` remains a reproducible template, not an attached Blueprint.

The GitHub Pages interface calls `https://kratos-personal-research.onrender.com`.
The same interface is also served directly at that address. At the owner's
request, `KRATOS_PUBLIC_ANALYSIS=true` permits on-demand ticker analysis without
a visitor token. This setting opens only `/api/analyze`; it does not grant
access to raw provider endpoints, provider diagnostics, or private historical
research. Those endpoints still require `KRATOS_ACCESS_TOKEN`.

Provider keys stay on the server. Requests remain rate-limited, analysis
concurrency is bounded, and API responses use `Cache-Control: no-store`.
This configuration does not confer redistribution or commercial data rights;
the application remains for personal research and retains source limitations.
Set `KRATOS_PUBLIC_ANALYSIS=false` and restore the Pages config's
`personal_access_required` flag to require a visitor token again.

The free server can sleep. Allow up to three minutes for a cold start plus an
analysis. Unsupported tickers and provider failures remain explicit errors.
This is no promise of live exchange entitlement, freshness or profitable signals.
Provider credentials stored as GitHub repository secrets do not automatically
transfer to Render. The current runtime uses the personal Yahoo fallback unless
account credentials and an explicit provider order are configured on Render.

Weekly completion checks now share one exchange-calendar lookup per batch,
instead of rebuilding the calendar for each historical week. Holiday and
closed-candle filtering remain enforced.
