"""Independent, free-data options positioning research.

This is NOT TerraShade code, a dealer position feed, or evidence of smart-money trades.
Open interest and implied volatility are vendor snapshots; dealer signs are UNKNOWN.
The published call-positive / put-negative book is a *scenario* only.

All calculations can be tested offline with deterministic fixtures.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timezone
from math import erf, exp, isfinite, log, pi, sqrt
from typing import Iterable


MULTIPLIER = 100
YEAR_DAYS = 365.25


def cdf(z: float) -> float:
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def pdf(z: float) -> float:
    return exp(-0.5 * z * z) / sqrt(2.0 * pi)


def greeks(spot: float, strike: float, iv: float, years: float,
           kind: str, rate: float = 0.04, yield_rate: float = 0.0) -> dict | None:
    """Black-Scholes European greeks; APPROXIMATION for American equity options.

    Vanna is change in delta per unit of IV; charm is delta change per day
    as calendar time advances. The model ignores dividends, early exercise
    and term structure unless explicit input assumptions are supplied.
    """
    vals = (spot, strike, iv, years, rate, yield_rate)
    if (kind not in ("call", "put") or not all(isfinite(float(v)) for v in vals)
        or spot <= 0 or strike <= 0 or iv <= 0.001 or years <= 0
        or iv > 10.0):
        return None
    root = sqrt(years)
    d1 = (log(spot / strike) + (rate - yield_rate + iv * iv / 2) * years) / (iv * root)
    d2 = d1 - iv * root
    discount = exp(-yield_rate * years)
    delta = discount * (cdf(d1) if kind == "call" else cdf(d1) - 1)
    gamma = discount * pdf(d1) / (spot * iv * root)
    vanna = -discount * pdf(d1) * d2 / iv
    dd1_dt = (rate - yield_rate + iv * iv / 2) / (2 * iv * root) - d1 / (2 * years)
    charm_day = -discount * (pdf(d1) * dd1_dt
                             - yield_rate * (cdf(d1) if kind == "call" else cdf(d1)-1)) / YEAR_DAYS
    return {"delta": delta, "gamma": gamma, "vanna": vanna, "charm_per_day": charm_day}


def _as_float(x, default=None):
    try:
        value = float(x)
        return value if isfinite(value) else default
    except (ValueError, TypeError):
        return default


def _midpoint(c: dict):
    bid = _as_float(c.get("bid"))
    ask = _as_float(c.get("ask"))
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    return (bid + ask) / 2


def exposure_book(spot: float, contracts: Iterable[dict], *, asof: datetime | None = None,
                  risk_free_rate: float = 0.04, dividend_yield: float = 0.0) -> dict:
    """Compute strike concentrations under explicit call + / put - OI convention.

    All contracts must have expiry YYYY-MM-DD, strike, type, open_interest, iv.
    We do NOT infer actual dealer exposure directions from open interest.
    """
    asof = asof or datetime.now(timezone.utc)
    if asof.tzinfo is None:
        raise ValueError("asof must be timezone-aware")
    if not isfinite(float(spot)) or spot <= 0:
        raise ValueError("spot must be finite and positive")
    strike_map = defaultdict(lambda: {"call_gex": 0.0, "put_gex": 0.0,
                                      "scenario_net_gex": 0.0, "gross_gex": 0.0,
                                      "scenario_dex": 0.0, "scenario_vex": 0.0,
                                      "scenario_charm": 0.0, "contracts": 0})
    by_expiry = defaultdict(dict)
    accepted = []
    rejected = 0
    earliest_trade = None
    latest_trade = None
    for c in contracts:
        try:
            kind = str(c["type"]).lower()
            strike = float(c["strike"])
            expiry = date.fromisoformat(str(c["expiry"]))
            oi = int(c["open_interest"])
            iv = float(c["iv"])
            # A stock-market cash session ends at 4 PM Eastern, subject to calendar changes.
            # Using 16:00 UTC here would be incorrect; timezone-aware expiry is required.
            from zoneinfo import ZoneInfo
            settle = datetime(expiry.year, expiry.month, expiry.day, 16, 0,
                              tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
            years = max(0, (settle - asof.astimezone(timezone.utc)).total_seconds()) / (YEAR_DAYS * 86400)
            if kind not in ("call", "put") or oi <= 0 or oi > 100_000_000:
                rejected += 1
                continue
            g = greeks(spot, strike, iv, years, kind, risk_free_rate, dividend_yield)
            if not g:
                rejected += 1
                continue
        except (ValueError, TypeError, KeyError, OverflowError):
            rejected += 1
            continue
        # Dollar gamma for a ONE PERCENT move in underlying; NOT a cash flow observation.
        gamma_usd = g["gamma"] * oi * MULTIPLIER * spot * spot * 0.01
        dex_usd = g["delta"] * oi * MULTIPLIER * spot
        vex_usd_per_iv_point = g["vanna"] * oi * MULTIPLIER * spot * 0.01
        charm_usd_per_day = g["charm_per_day"] * oi * MULTIPLIER * spot
        sign = 1 if kind == "call" else -1
        z = strike_map[strike]
        z[f"{kind}_gex"] += gamma_usd
        z["scenario_net_gex"] += sign * gamma_usd
        z["gross_gex"] += abs(gamma_usd)
        z["scenario_dex"] += sign * dex_usd
        z["scenario_vex"] += sign * vex_usd_per_iv_point
        z["scenario_charm"] += sign * charm_usd_per_day
        z["contracts"] += 1
        accepted.append({"expiry": str(expiry), "strike": strike, "type": kind,
                         "open_interest": oi, "iv": iv, "gamma_usd": gamma_usd,
                         "price_mid": _midpoint(c)})
        key = str(expiry)
        row = by_expiry[key].setdefault(str(strike), 0.0)
        by_expiry[key][str(strike)] = row + sign * gamma_usd
        t = c.get("last_trade_at_utc")
        if t:
            stamp = str(t)
            earliest_trade = min(earliest_trade or stamp, stamp)
            latest_trade = max(latest_trade or stamp, stamp)

    levels = sorted(({"strike": s, **v} for s, v in strike_map.items()),
                    key=lambda o: o["strike"])
    top = sorted(levels, key=lambda x: x["gross_gex"], reverse=True)
    above = [x for x in levels if x["strike"] >= spot]
    below = [x for x in levels if x["strike"] <= spot]
    call_wall = max(above, key=lambda x: x["call_gex"])["strike"] if above and any(x["call_gex"]>0 for x in above) else None
    put_wall = max(below, key=lambda x: x["put_gex"])["strike"] if below and any(x["put_gex"]>0 for x in below) else None

    # Flip is model-dependent, using static OI and IV and call+ / put- sign.
    flip = None
    if len(accepted) >= 2 and any(c["type"] == "call" for c in accepted) and any(c["type"] == "put" for c in accepted):
        grid = [spot*(0.85 + 0.30*i/60) for i in range(61)]
        totals = []
        for hypothetical in grid:
            total = 0.0
            for c in accepted:
                from zoneinfo import ZoneInfo
                expiry = date.fromisoformat(c["expiry"])
                settle = datetime(expiry.year, expiry.month, expiry.day, 16,
                                  tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
                yrs = (settle-asof.astimezone(timezone.utc)).total_seconds()/(86400*YEAR_DAYS)
                g = greeks(hypothetical, c["strike"], c["iv"], yrs, c["type"], risk_free_rate, dividend_yield)
                if g:
                    total += (1 if c["type"] == "call" else -1)*g["gamma"]*c["open_interest"]*MULTIPLIER*hypothetical*hypothetical*.01
            totals.append(total)
        roots = []
        for i in range(1, len(grid)):
            a,b=totals[i-1],totals[i]
            if (a<0<b or a>0>b) and b!=a:
                roots.append(grid[i-1]+(0-a)*(grid[i]-grid[i-1])/(b-a))
        if roots:
            flip = min(roots, key=lambda p:abs(p-spot))
    # Shortest listed expiry's ATM straddle, only with REAL positive bid+ask quotes.
    atm_move = None
    expiries = sorted({x["expiry"] for x in accepted})
    if expiries:
        e=expiries[0]
        near=sorted({x["strike"] for x in accepted if x["expiry"]==e},key=lambda k:abs(k-spot))
        for k in near:
            cs=[x for x in accepted if x["expiry"]==e and x["strike"]==k]
            call=next((c for c in cs if c["type"]=="call" and c["price_mid"] is not None),None)
            put=next((c for c in cs if c["type"]=="put" and c["price_mid"] is not None),None)
            if call and put:
                atm_move={"expiry":e, "strike":k, "straddle_mid":call["price_mid"]+put["price_mid"],
                          "illustrative_85pct_straddle_move":.85*(call["price_mid"]+put["price_mid"]),
                          "quote_timestamps_unverified":True}
                break
    return {
        "spot": float(spot), "asof_utc": asof.astimezone(timezone.utc).isoformat(),
        "valid_contracts": len(accepted), "rejected_contracts": rejected,
        "coverage_expiries": sorted(by_expiry), "scenario_assumption": "Calls positive / puts negative: unverified dealer position convention",
        "risk_free_rate_assumed": risk_free_rate, "dividend_yield_assumed": dividend_yield,
        "source_trade_time_oldest": earliest_trade, "source_trade_time_newest": latest_trade,
        "net_scenario_gex_1pct_usd": sum(x["scenario_net_gex"] for x in levels),
        "net_scenario_dex_usd": sum(x["scenario_dex"] for x in levels),
        "net_scenario_vex_1ivpoint_usd": sum(x["scenario_vex"] for x in levels),
        "net_scenario_charm_1day_usd": sum(x["scenario_charm"] for x in levels),
        "king_strike_by_gross_gex": top[0]["strike"] if top else None,
        "call_wall_strike": call_wall, "put_wall_strike": put_wall,
        "scenario_gamma_flip": flip, "atm_straddle": atm_move,
        "strike_exposure": levels, "expiry_exposure": dict(by_expiry),
        "interpretation": "OI-based sensitivity scenario. No directional trade recommendation. Dealer positions, gamma hedging trades and price magnetism are not verified."
    }


def fetch_free_options(symbol: str, *, expiries_limit: int = 3,
                       risk_free_rate: float = 0.04, dividend_yield: float = 0.0) -> dict:
    """Retrieve a small set of Yahoo option chains with yfinance (unofficial).

    Returned quote last-trade date is NOT reliable open-interest update time.
    Real-time claims, complete coverage and redistribution are not warranted.
    """
    if not isinstance(symbol,str) or not symbol or len(symbol)>20:
        raise ValueError("Invalid ticker")
    from .data import valid_symbol
    ticker = valid_symbol(symbol)
    import yfinance as yf
    now = datetime.now(timezone.utc)
    client = yf.Ticker(ticker)
    choices = list(client.options or [])[:max(1,min(6,expiries_limit))]
    if not choices:
        raise ValueError("No options expirations returned by provider")
    # Fast quote may be delayed; prefer prior close from daily history with provenance.
    d=client.history(period="7d",interval="1d",auto_adjust=False,prepost=False,timeout=15)
    if d.empty:
        raise ValueError("No actual underlying close from provider")
    spot=float(d["Close"].dropna().iloc[-1])
    rows=[]
    for expiry in choices:
        try:
            chain=client.option_chain(expiry)
        except Exception as exc:
            # Missing expiry is not a zero-exposure expiration.
            continue
        for typ,frame in (("call",chain.calls),("put",chain.puts)):
            if frame is None:
                continue
            for _,z in frame.iterrows():
                stamp=z.get("lastTradeDate")
                try:
                    t=stamp.isoformat() if stamp is not None and not str(stamp)=="NaT" else None
                except Exception:
                    t=None
                rows.append({
                    "expiry":expiry,"type":typ,"strike":z.get("strike"),
                    "open_interest":z.get("openInterest"),"iv":z.get("impliedVolatility"),
                    "bid":z.get("bid"),"ask":z.get("ask"),
                    "last_trade_at_utc":t
                })
    if not rows:
        raise ValueError("Option chain unavailable or incomplete")
    result=exposure_book(spot,rows,asof=now,risk_free_rate=risk_free_rate,dividend_yield=dividend_yield)
    if result["valid_contracts"]==0:
        raise ValueError("No valid contracts, implied volatility or open interest")
    result.update({
        "ticker":ticker,"provider":"Yahoo Finance via yfinance (unofficial/delayed; subject to availability)",
        "underlying_daily_close_date":str(d.index[-1].date()),
        "underlying_is_last_daily_close":True,"option_chain_retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
        "requested_expiries":choices,
        "expiry_coverage":len(result["coverage_expiries"]),
        "license_note":"Check data-source redistribution terms before republishing derived live option-chain values."
    })
    return result
