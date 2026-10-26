# Hosted personal analysis

Render service: `kratos-personal-research` in the confirmed My Workspace.
Runtime is Python on Render's free web-service plan in Ohio. No paid database,
disk, worker or scheduled task was created. This service was created directly;
`render.yaml` remains a reproducible template, not an attached Blueprint.

The GitHub Pages interface calls `https://kratos-personal-research.onrender.com`.
The same interface is also served directly at that address. A service-specific
access token protects personal-use data. The token is stored in Render's
Environment settings as `KRATOS_ACCESS_TOKEN`; copy it into the password field
in the interface. It is sent as an Authorization header, kept only in page
memory, and never embedded in a public link, source file or GitHub Pages config.
Provider API keys never belong in this field.

The free server can sleep. Allow up to three minutes for a cold start plus an
analysis. Unsupported tickers and provider failures remain explicit errors.
This is no promise of live exchange entitlement, freshness or profitable signals.
Provider credentials stored as GitHub repository secrets do not automatically
transfer to Render. The current runtime uses the personal Yahoo fallback unless
account credentials and an explicit provider order are configured on Render.

Weekly completion checks now share one exchange-calendar lookup per batch,
instead of rebuilding the calendar for each historical week. Holiday and
closed-candle filtering remain enforced.
