"""Publish source-backed KRATOS analysis snapshots and forward forecast ledger.

Static Pages frontend reads these files. No invented prices, odds or backtests.
Runs in GitHub Actions; updates are observational, not real-time entitlements.
"""
import json
import math
import os
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from kratos.engine import analyze
from kratos.technicals import only_closed_daily
from kratos.calendar import schedule
from kratos.structure import causal_structure
from kratos import audit as event_audit
from kratos.truth import build_evidence_report
import tempfile

ET = ZoneInfo("America/Toronto")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
SNAPSHOTS = DATA / "snapshots.json"
LEDGER = DATA / "ledger.json"
DEFAULT = "NVDA,AVGO,AMAT,MU,CIFR,IREN,CRWV,NBIS,USAR,AXTI,GOOG,UBER"


def clean(v):
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            return clean(v.item())
        except (ValueError, TypeError):
            pass
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def iso_timestamp(idx):
    if len(idx) == 0:
        return None
    stamp = idx[-1]
    if getattr(stamp, "tzinfo", None) is None:
        return None
    return stamp.tz_convert("UTC").isoformat()


def pack(ticker, result):
    snap, tech, decision = result.snapshot, result.technical, result.decision
    df = tech["daily"]
    currency = snap.fundamentals.get("currency")
    history = []
    for index, row in df.tail(120).iterrows():
        c = float(row["Close"])
        if math.isfinite(c):
            history.append({"date": str(index.date()), "close": round(c, 5)})
    return clean({
        "ticker": ticker,
        "provider": snap.provider,
        "currency": currency,
        "quote": snap.quote,
        "provenance": snap.provenance,
        "corporate_actions": snap.actions,
        "analysis_version": event_audit.MODEL_VERSION,
        "truth": build_evidence_report(snap, tech, decision),
        "signal_at_utc": tech.get("signal_at_utc"),
        "session_schedule": [{"date":str(day.date()),"open_utc":row.market_open.isoformat(),"close_utc":row.market_close.isoformat()} for day,row in schedule(ticker, snap.retrieved_at.date()-timedelta(days=2),snap.retrieved_at.date()+timedelta(days=14)).iterrows()],
        "retrieved_at_utc": snap.retrieved_at.isoformat(),
        "minute_bar_utc": iso_timestamp(snap.minute.index),
        "price": tech["close"],
        "last_closed_bar_date": tech["asof_bar_date"],
        "freshness_at_build": result.freshness,
        "decision": decision,
        "technical": {
            "asof_bar_date": tech["asof_bar_date"],
            "trends": tech["trends"],
            "atr": tech["atr"], "rsi": tech["rsi"],
            "ema20": tech["ema20"], "ema50": tech["ema50"],
            "volume_ratio": tech["volume_ratio"],
            "support20": tech["support20"],
            "resistance20": tech["resistance20"],
            "resistance60": tech["resistance60"],
            "high52w": tech["high52w"], "low52w": tech["low52w"],
            "history": history,
            "structure": tech.get("structure", {}),
            "candles": {tf:[{"time":i.isoformat(), "open":r.Open,"high":r.High,"low":r.Low,"close":r.Close,"volume":r.Volume} for i,r in frame.tail(100).iterrows()] for tf,frame in tech.get("frames",{}).items()}
        },
        "market_structure": causal_structure(df),
        "fundamentals": {
            "facts": [{"label": k, "value": v} for k, v in result.facts],
            "valuation_note": result.valuation_note
        },
        "warnings": snap.warnings,
        "error": None
    })


def audit_summary(path):
    stats=event_audit.audit_stats(path)
    history=event_audit.records(path)
    keys=('total','resolved','direction_evaluated','direction_wins','range_evaluated','range_hits')
    summary={k:sum(s.get(k,0) for s in stats.values()) for k in keys}
    summary['by_horizon']={str(k):v for k,v in stats.items()}
    summary['validation_status']='INSUFFICIENT VALIDATION'
    summary['recent']=[dict(ticker=p['ticker'],recorded_at_utc=p['recorded_at_utc'],
        horizon_sessions=p['horizon_sessions'],bias=p['bias'],forecast_id=p['forecast_id'],
        model_version=p['model_version'],status=(p['outcome'] or {}).get('status','OPEN'),
        direction_correct=(p['outcome'] or {}).get('direction_correct')) for p in history[-25:][::-1]]
    summary['method']='Endpoint direction vs frozen observed reference; not executable returns. No calibrated probabilities or grades.'
    return summary


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(symbols=None, analyzer=analyze):
    from filelock import FileLock
    DATA.mkdir(parents=True,exist_ok=True)
    with FileLock(str(DATA/'publisher.lock'), timeout=1):
        return _run_locked(symbols,analyzer)


def _run_locked(symbols=None, analyzer=analyze):
    symbols=symbols or [s.strip().upper() for s in os.getenv('KRATOS_SYMBOLS',DEFAULT).split(',') if s.strip()]
    previous=read_json(SNAPSHOTS,{'tickers':{}}).get('tickers',{})
    events_path=DATA/'events.jsonl'
    # Audit corruption is a hard failure. Never silently replace the event history.
    original_text=events_path.read_text() if events_path.exists() else ''
    events=[json.loads(line) for line in original_text.splitlines() if line]
    tickers={};success=new=resolved=0
    research={}
    research_symbols=set(os.getenv("KRATOS_RESEARCH_SYMBOLS", "NVDA").split(","))
    with tempfile.TemporaryDirectory() as temp:
        db=str(Path(temp)/'audit.sqlite3')
        event_audit.import_events(events,db)
        for ticker in dict.fromkeys(symbols):
            print('Fetching',ticker,flush=True)
            try:
                result=analyzer(ticker)
                # Validate market evidence before marking the ticker refreshed.
                # A failed truth check is a per-ticker failure, not a synthetic result.
                packed=pack(ticker,result)
            except Exception as exc:
                detail=f'{type(exc).__name__}: {str(exc)[:200]}'
                if ticker in previous and not previous[ticker].get('error'):
                    old=previous[ticker].copy();old['warnings']=list(old.get('warnings',[]))+['LATEST REFRESH FAILED: '+detail]
                    old['refresh_failed']=True;tickers[ticker]=old
                else: tickers[ticker]={'ticker':ticker,'error':detail}
                print('ERROR',ticker,detail,flush=True);continue
            tickers[ticker]=packed
            if ticker in research_symbols:
                from kratos.research import walk_forward
                research[ticker]={str(h):walk_forward(result.technical['daily'],h) for h in (5,20)}
            now=datetime.now(timezone.utc)  # After fetching, never backdate a forecast to job start.
            resolved+=event_audit.resolve(ticker,result.snapshot.daily,db,now=now,actions=result.snapshot.actions)
            try: new+=len(event_audit.record(ticker,clean({k:v for k,v in result.technical.items() if k not in ('daily','frames')}),result.decision,result.snapshot.provider,db,now=now))
            except ValueError as exc: tickers[ticker]['warnings'].append('Forecast not recorded: '+str(exc))
            success+=1
        updated=event_audit.export_events(db)
        event_audit.verify_events(updated)
        assert updated[:len(events)]==events
        DATA.mkdir(parents=True,exist_ok=True)
        if (events_path.read_text() if events_path.exists() else '') != original_text:
            raise RuntimeError('Audit history changed concurrently; refusing to append a fork.')
        if len(updated)>len(events):
            with events_path.open('a') as stream:
                for e in updated[len(events):]: stream.write(event_audit.canonical(e)+'\n')
        summary=audit_summary(db)
        legacy=read_json(LEDGER,[])
        summary['legacy_unvalidated_count']=len(legacy)
        archive=DATA/'predeployment-events.jsonl'
        summary['predeployment_unscored_events']=len(archive.read_text().splitlines()) if archive.exists() else 0
        if research: write_json(DATA/'research.json',{'generated_at_utc':datetime.now(timezone.utc).isoformat(),'experiments':research})
        write_json(SNAPSHOTS,{'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'provider_note':'Yahoo unofficial; no licensed-live agreement or freshness guarantee.',
            'coverage':len(tickers),'fresh_results':success,'tickers':tickers,'audit':summary,
            'analysis_version':event_audit.MODEL_VERSION})
    print(f'Published {len(tickers)} symbols, {success} fetched, {new} new observations, {resolved} resolved',flush=True)

if __name__=='__main__': run()
