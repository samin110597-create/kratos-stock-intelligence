"""Local/Spaces Gradio user interface. Start with: python app.py"""
from __future__ import annotations
import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import gradio as gr
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from kratos.audit import record, resolve, audit_stats, recent_records
from kratos.engine import analyze
from kratos.data import valid_symbol
from kratos.technicals import finite
from kratos.options_ui import fetch_options_ui
from kratos.structure import causal_structure

ET = ZoneInfo("America/Toronto")

CSS = """
.gradio-container {max-width: 1250px !important; margin:auto !important;}
.kr-title {font-size:30px;font-weight:850;letter-spacing:-.5px}
.kr-sub {opacity:.73;font-size:14px;margin-bottom:12px}
.kpi-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:12px 0}
.kpi {border:1px solid #7286a63d;background:#8198a409;border-radius:14px;padding:15px}
.kpi .v {font-size:22px;font-weight:800;margin:6px 0}
.kpi .k {font-size:12px;opacity:.7;letter-spacing:.6px}
.kr-note {border-left:3px solid #6b90b8;padding:8px 14px;background:#7286a610;margin:12px 0}
"""


def money(v):
    return f"{v:,.2f}" if finite(v) else "n/a"


def esc(v):
    return html.escape(str(v))


def plot_price(t):
    frame = t["daily"].tail(160)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.035,
                        row_heights=[.76,.24])
    fig.add_trace(go.Candlestick(x=frame.index, open=frame["Open"],high=frame["High"],
                    low=frame["Low"],close=frame["Close"],name="Daily bars"),row=1,col=1)
    for name,color in [("EMA20","#23a7a6"),("EMA50","#f5b642")]:
        fig.add_trace(go.Scatter(x=frame.index,y=frame[name],name=name,
                      line={"width":1.7,"color":color}),row=1,col=1)
    fig.add_trace(go.Bar(x=frame.index,y=frame["Volume"],name="Volume",
                        marker_color="#6d91b8"),row=2,col=1)
    fig.update_layout(height=490, margin=dict(l=20,r=15,t=10,b=10),
                      template="plotly_dark",paper_bgcolor="#101824",plot_bgcolor="#101824",
                      xaxis_rangeslider_visible=False,legend=dict(orientation="h",y=1.05),
                      hovermode="x unified")
    fig.update_yaxes(title_text="Price",row=1,col=1)
    fig.update_yaxes(title_text="Vol",row=2,col=1)
    return fig


def result_view(r):
    t, dec, fresh = r.technical, r.decision, r.freshness
    source_time = r.snapshot.retrieved_at.astimezone(ET).strftime("%Y-%m-%d %I:%M:%S %p %Z")
    cards=[("RULE RESULT",dec["classification"]),("LAST DAILY CLOSE",money(t["close"])),
           ("DAILY RSI",money(t["rsi"])), ("ATR / DAY",money(t["atr"])),
           ("D / W MOVING AVERAGES",f"{t['trends']['1D']} / {t['trends']['1W']}"),
           ("DATA FRESHNESS",fresh["status"].split(" — ")[0])]
    blocks = "".join(f'<div class="kpi"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>' for k,v in cards)
    header = f'<div class="kr-title">KRATOS / {esc(r.snapshot.ticker)}</div><div class="kr-sub">{esc(r.snapshot.provider)} · Fetch: {esc(source_time)} · Last closed/available daily bar: {esc(t["asof_bar_date"])} · Minute bar: {esc(fresh["last_bar"] or "unavailable")}</div><div class="kpi-grid">{blocks}</div>'
    reasons = "\n".join(f"- {x}" for x in dec["reasons"])
    z = dec["entry_zone"]
    zone = f"{money(z[0])} – {money(z[1])}" if z else "Unavailable"
    ts = ", ".join(money(x) for x in dec["targets"]) if dec["targets"] else "Unavailable"
    rr = f"{dec['rr_to_resistance']:.2f}R" if finite(dec["rr_to_resistance"]) else "n/a"
    summary=(f"### {dec['classification']} — {dec['bias']} context\n"
             f"{dec.get('summary','')}\n\n{dec.get('next_action','')}\n\n"
             f"**Illustrative entry zone:** {zone} · **Invalidation reference:** {money(dec['stop'])} · **Observed chart targets:** {ts}\n\n"
             f"**Room to first resistance after assumed costs:** {rr}\n\n"
             f"{reasons}\n\n"
             f"> The price levels are computed from daily bars, not executable limit orders. No entry recommendation when data is stale or market closed. No probabilities or proven edge are claimed.")
    technical=("### Confirmed-bar technical report\n\n"
               "| Timeframe | Price structure | What it means |\n|---|---|---|\n" + "\n".join(f"| {key} | {item['state']} | {item['explanation']} |" for key,item in dec["timeframes"].items())+
               "\n\n" + f"**20-day support:** {money(t['support20'])} · **20-day resistance:** {money(t['resistance20'])} · **60-day high:** {money(t['resistance60'])}\n\n"+
               f"**52-week range:** {money(t['low52w'])} – {money(t['high52w'])} · **EMA20:** {money(t['ema20'])} · **EMA50:** {money(t['ema50'])}\n\n"+
               f"**Relative daily volume:** {money(t['volume_ratio'])}× 20-day average.\n\n"
               "Missing intraday bars produce UNKNOWN, never fabricated indicators. Only complete exchange weeks are included.")
    structure=causal_structure(t["daily"])
    recent_gaps=structure.get("fvg", [])
    technical += ("\n\n### Price-action and liquidity context — observed closed bars\n\n"
                  + f"**Latest event:** {structure.get('status','UNKNOWN')} — {structure.get('reason','')}\n\n"
                  + f"**Prior 20-bar high/low:** {money(structure.get('reference_high'))} / "
                  + f"{money(structure.get('reference_low'))}\n\n"
                  + f"**Relative volume confirmation:** {structure.get('participation','UNKNOWN')}\n\n"
                  + f"**Confirmed swing-high / swing-low sequence:** "
                  + f"{structure.get('confirmed_pivot_trend',{}).get('highs','UNKNOWN')} / "
                  + f"{structure.get('confirmed_pivot_trend',{}).get('lows','UNKNOWN')}\n\n"
                  + "**Recent still-unfilled FVG price patterns:**\n"
                  + ("\n".join(f"- {g['kind']}: {money(g['low'])}–{money(g['high'])}, "
                                f"created {g['created_on']} ({g['state']})"
                                for g in recent_gaps) if recent_gaps else "- None meeting the testable size filter.") 
                  + "\n\n*These patterns do not prove institutional orders or offer validated probabilities.*")
    facts = "| Fundamental fact | Reported value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k,v in r.facts)
    fundamentals = ("### Fundamentals — from data provider\n\n" + facts + "\n\n**Valuation:** " + r.valuation_note +
                    "\n\nAmounts and currency follow the provider and must be independently verified against filings. Data may be delayed or missing.")
    outlook="### Conditional price paths\n\n"+"\n\n".join(f"**{name.title()}:** {text}" for name,text in dec.get('scenarios',{}).items())
    outlook+="\n\n"+dec.get('review_horizon','')+" No calibrated arrival date or probability is claimed."
    warnings = "\n".join(f"- {w}" for w in r.snapshot.warnings) or "- None reported (does not guarantee data quality)."
    quality=(f"### Data quality and limitations\n\n**Reported minute-bar age:** {fresh['age_minutes']} min · **Status:** {fresh['status']}\n\n"
             f"**Provider errors:**\n{warnings}\n\n"
             "NYSE/TSX holiday calendars enabled. No licensed options/dark-pool feeds, no institutional flow, no audited intrinsic value, no intraday backtesting, and no trained ML model in this MVP. "
             "The original aiappsgbb/kratos-agent requires a substantially different Foundry/Copilot infrastructure; this MVP follows its one-orchestrator/many-skills pattern only.")
    state={"ticker":r.snapshot.ticker,"tech":{k:v for k,v in t.items() if k not in ("daily", "frames")},
           "decision":dec,"provider":r.snapshot.provider}
    return header,summary,technical,fundamentals,outlook,quality,plot_price(t),state


def user_analyze(ticker):
    try:
        r = analyze(valid_symbol(ticker))
        return (*result_view(r), "Analysis loaded. To freeze this hypothesis, click Record forecast.")
    except Exception as exc:
        return ("<h3>Market data unavailable</h3>",
                f"**No signal issued.** {type(exc).__name__}: {str(exc)[:270]}",
                "Data unavailable.","Data unavailable.","No projection issued.",
                "Check the ticker or retry when the provider is accessible.",
                None,None,"Nothing was recorded.")


def save_hypothesis(state):
    if not state or not state.get("tech"):
        return "Analyze a ticker first. Nothing saved.",*refresh_audit()
    try:
        added=record(state["ticker"],state["tech"],state["decision"],state["provider"])
        msg = (f"Recorded forecast IDs {added}. The prediction is now frozen; outcomes will be evaluated against later sessions."
               if added else "Already recorded this ticker/date/horizon/version. Previous forecast remains unchanged.")
        return msg,*refresh_audit()
    except Exception as exc:
        return f"Database write failed: {type(exc).__name__}: {exc}",*refresh_audit()


def refresh_audit():
    stats = audit_stats()
    if not stats:
        summary="No forecasts saved yet. There is **no measured accuracy**."
    else:
        summary="\n".join(
            f"**{h}-session:** {s['resolved']}/{s['total']} resolved · "
            + (f"direction correct {s['direction_wins']}/{s['direction_evaluated']} "
               f"({s['direction_wins']/s['direction_evaluated']:.1%})" if s['direction_evaluated'] else "direction accuracy unavailable")
            + f" · ATR envelope endings inside range {s['range_hits']}/{s['resolved']}" for h,s in stats.items())
    records=recent_records()
    frame=pd.DataFrame(records,columns=["Ticker","Source bar","Horizon","Bias","Call","Close",
                "Status","Outcome date","Outcome close","Direction correct","Band lower","Band upper"])
    return summary,frame


def verify_outcomes(ticker):
    try:
        r=analyze(valid_symbol(ticker))
        n=resolve(r.snapshot.ticker, r.snapshot.daily)
        return f"Updated {n} matured forecasts for {r.snapshot.ticker}. Incomplete/current-day outcome bars are excluded.",*refresh_audit()
    except Exception as exc:
        return f"Update failed: {type(exc).__name__}: {str(exc)[:200]}",*refresh_audit()


def build_app():
    with gr.Blocks(title="KRATOS Stock Intelligence") as ui:
        gr.HTML('<div class="kr-title">KRATOS <span style="color:#19b6bb">/</span> STOCK INTELLIGENCE</div><div class="kr-sub">Independent research engine · Any ticker · Honest data freshness · Prediction audit · v0.2</div>')
        with gr.Row():
            ticker=gr.Textbox(value="NVDA",label="Enter ticker",placeholder="NVDA, CIFR, MU, RY.TO",scale=5)
            analyze_btn=gr.Button("Analyze",variant="primary",scale=1)
        banner=gr.HTML("<p>Enter a ticker and click Analyze. Prices are fetched only when requested; nothing is fabricated.</p>")
        with gr.Tabs():
            with gr.Tab("Decision"):
                decision=gr.Markdown("Run analysis to see your rule-based decision.")
                chart=gr.Plot(label="Daily price / volume")
            with gr.Tab("Technicals"):
                tech=gr.Markdown("Run analysis first.")
            with gr.Tab("Fundamentals"):
                fundamentals=gr.Markdown("Run analysis first.")
            with gr.Tab("Projection"):
                projection=gr.Markdown("Run analysis first.")
            with gr.Tab("Options map · experimental"):
                gr.Markdown("**Personal-use options research from free, possibly delayed chains.** "
                            "Modeled GEX/VEX/DEX/Charm are NOT verified dealer positions. "
                            "This feature runs here in Python, not on the static GitHub Pages website.")
                options_btn=gr.Button("Fetch options positioning for ticker",variant="secondary")
                options_summary=gr.Markdown("Click Fetch to inspect available chains and modeled exposures.")
                options_chart=gr.Plot(label="Assumed dealer-sign gamma scenario")
                options_table=gr.Dataframe(label="Nearby strike gamma concentrations",interactive=False)
            with gr.Tab("Accuracy audit"):
                gr.Markdown("Forecasts are immutable. Statistics apply **only to matured, logged forecasts**, never invented historical wins. Outcomes use the 5th/20th future daily bar.")
                save_btn=gr.Button("Record this forecast",variant="secondary")
                settle_btn=gr.Button("Check completed outcomes for entered ticker")
                audit_msg=gr.Markdown("No action taken.")
                audit_summary=gr.Markdown("Press Refresh audit.")
                audit_table=gr.Dataframe(label="Prediction ledger",interactive=False)
                refresh_btn=gr.Button("Refresh audit")
            with gr.Tab("Data / Method"):
                quality=gr.Markdown("Run analysis for data-quality details.")
                gr.Markdown("[Original Kratos Agent reference](https://github.com/aiappsgbb/kratos-agent) · This independent research MVP does not install the original Microsoft hosted agent. No Vercel, auto-trades or investment guarantees.")
        state=gr.State()
        status=gr.Markdown("Ready.")
        analyze_btn.click(user_analyze,inputs=[ticker],outputs=[banner,decision,tech,fundamentals,
                      projection,quality,chart,state,status],show_progress="full")
        ticker.submit(user_analyze,inputs=[ticker],outputs=[banner,decision,tech,fundamentals,
                      projection,quality,chart,state,status])
        options_btn.click(fetch_options_ui,inputs=[ticker],
                          outputs=[options_summary,options_chart,options_table],show_progress="full")
        save_btn.click(save_hypothesis,inputs=[state],outputs=[audit_msg,audit_summary,audit_table])
        refresh_btn.click(refresh_audit,outputs=[audit_summary,audit_table])
        settle_btn.click(verify_outcomes,inputs=[ticker],outputs=[audit_msg,audit_summary,audit_table])
    return ui

if __name__ == "__main__":
    app=build_app()
    app.launch(server_name="0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1",
               server_port=int(os.getenv("PORT", "7860")),share=False,
               css=CSS,theme=gr.themes.Soft())
