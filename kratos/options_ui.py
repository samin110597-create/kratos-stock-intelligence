"""Gradio personal-use options research; no publicly republished options feed."""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
from .data import valid_symbol
from .options_research import fetch_free_options

def num(value, digits=2):
    return "Unavailable" if value is None else f"{value:,.{digits}f}"

def fetch_options_ui(ticker: str):
    """Return Markdown / chart / strike detail; errors never become zero exposure."""
    try:
        result=fetch_free_options(valid_symbol(ticker), expiries_limit=3)
    except Exception as exc:
        return (
            f"### Options data unavailable\n\n**{type(exc).__name__}:** {str(exc)[:260]}\n\n"
            "No GEX, VEX, DEX, Charm, walls, or probabilities calculated. "
            "This is a personal-use model, not a licensed public live options feed.",
            None,
            pd.DataFrame(columns=["Strike","Call GEX","Put GEX","Scenario Net GEX","Gross GEX","Contracts"])
        )
    r=result
    fetched=datetime.fromisoformat(r["option_chain_retrieved_at_utc"]).astimezone(
        ZoneInfo("America/Toronto")).strftime("%Y-%m-%d %I:%M %p %Z")
    details=[
        f"### {r['ticker']} · Free options positioning scenario",
        f"**Underlying last completed DAILY close:** USD {num(r['spot'])} "
        f"({r['underlying_daily_close_date']}). Not a live trade price.",
        f"**Fetched:** {fetched} · **Source:** {r['provider']}",
        f"**Coverage:** {r['valid_contracts']} qualifying contracts across "
        f"{r['expiry_coverage']} fetched expirations; {r['rejected_contracts']} rejected. "
        "This is not the complete options market.",
        f"**Largest gross gamma concentration:** {num(r['king_strike_by_gross_gex'])} · "
        f"**Call OI-gamma wall:** {num(r['call_wall_strike'])} · "
        f"**Put OI-gamma wall:** {num(r['put_wall_strike'])}",
        f"**Modeled gamma-flip strike:** {num(r['scenario_gamma_flip'])} "
        "(conditional on unverified positioning assumptions)",
        f"**GEX for 1% spot move:** {num(r['net_scenario_gex_1pct_usd'],0)} USD · "
        f"**DEX:** {num(r['net_scenario_dex_usd'],0)} USD",
        f"**VEX per 1 IV point:** {num(r['net_scenario_vex_1ivpoint_usd'],0)} USD · "
        f"**Charm per day:** {num(r['net_scenario_charm_1day_usd'],0)} USD"
    ]
    if r["atm_straddle"]:
        q=r["atm_straddle"]
        details.append(f"**Quoted-straddle sensitivity:** ±{num(q['illustrative_85pct_straddle_move'])} "
                       f"USD for expiry {q['expiry']} (strike {q['strike']}); "
                       "quote timestamps are NOT verified.")
    else:
        details.append("**Options-implied move:** Unavailable; no valid positive bid/ask ATM straddle.")
    details.extend([
        "**IMPORTANT:** Options open interest does NOT reveal whether dealers are long or short. "
        "This model assumes calls positive, puts negative. It is not proof of dealer hedging. "
        "Options quotes and open interest may be delayed. Greek sensitivities use "
        "Black-Scholes assumptions and do not account for American-style early exercise. "
        "These levels are NOT guaranteed magnets, support, resistance, or predictions.",
        "**No BUY/SELL signal or accuracy percentage is issued by this module.** "
        "Confirm price-action structure and catalyst risk separately."
    ])
    rows=r["strike_exposure"]
    table=pd.DataFrame([{
        "Strike":x["strike"],"Call GEX":round(x["call_gex"]),
        "Put GEX":round(x["put_gex"]),"Scenario Net GEX":round(x["scenario_net_gex"]),
        "Gross GEX":round(x["gross_gex"]),"Contracts":x["contracts"]
    } for x in sorted(rows,key=lambda x:abs(x["strike"]-r["spot"]))[:45]])
    nearby=sorted(sorted(rows,key=lambda x:abs(x["strike"]-r["spot"]))[:36],
                  key=lambda x:x["strike"])
    fig=go.Figure()
    fig.add_trace(go.Bar(x=[x["strike"] for x in nearby],
                         y=[x["scenario_net_gex"] for x in nearby],
                         name="Call + / put - GEX scenario",
                         marker_color=["#56d3c3" if x["scenario_net_gex"]>=0 else "#ab7aff" for x in nearby]))
    fig.add_vline(x=r["spot"],line_dash="dot",line_color="white",
                  annotation_text="Last daily close")
    fig.update_layout(template="plotly_dark",height=420,
                      title="OI-based modeled gamma by strike — not actual dealer positions",
                      xaxis_title="Strike",yaxis_title="Modeled GEX USD / 1% stock move",
                      paper_bgcolor="#111c2b",plot_bgcolor="#111c2b",
                      margin=dict(l=35,r=20,t=50,b=45))
    return "\n\n".join(details), fig, table
