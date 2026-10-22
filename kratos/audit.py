"""Append-only, hash-chained forecasts and separate outcomes. Legacy rows stay unscored.

Hashes detect accidental alteration, not a malicious database administrator. Durable
hosting/backup is a deployment responsibility, disclosed by the API health endpoint.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import sqlite3
import pandas as pd
from .calendar import schedule, utc, ET, session_state
from .technicals import only_closed_daily

MODEL_VERSION='rules-v2.0.0'

def canonical(value):
    def default(v):
        if hasattr(v,'item'): return v.item()
        if hasattr(v,'isoformat'): return v.isoformat()
        raise TypeError(f'Unsupported audit value: {type(v).__name__}')
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,default=default)

def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()

def db_file():
    root=Path(os.getenv('KRATOS_DB_DIR','data'));root.mkdir(parents=True,exist_ok=True)
    return str(root/'forecasts.sqlite3')

def connect(path=None):
    db=sqlite3.connect(path or db_file(),timeout=10)
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS events (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT NOT NULL UNIQUE,
      kind TEXT NOT NULL CHECK(kind IN ('forecast','outcome')),
      forecast_id TEXT NOT NULL,
      payload TEXT NOT NULL,
      previous_hash TEXT NOT NULL,
      event_hash TEXT NOT NULL UNIQUE,
      UNIQUE(kind,forecast_id)
    );
    CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
      BEGIN SELECT RAISE(ABORT,'Published audit events are immutable'); END;
    CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
      BEGIN SELECT RAISE(ABORT,'Published audit events are immutable'); END;
    ''')
    return db

def _append(db,kind,forecast_id,payload):
    event_id=f'{kind}:{forecast_id}'
    if db.execute('SELECT 1 FROM events WHERE event_id=?',(event_id,)).fetchone(): return False
    if kind=='outcome' and not db.execute("SELECT 1 FROM events WHERE kind='forecast' AND forecast_id=?",(forecast_id,)).fetchone():
        raise ValueError('Outcome has no original forecast.')
    last=db.execute('SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
    previous=last[0] if last else '0'*64
    body={'event_id':event_id,'kind':kind,'forecast_id':forecast_id,'payload':payload,'previous_hash':previous}
    db.execute('INSERT INTO events(event_id,kind,forecast_id,payload,previous_hash,event_hash) VALUES(?,?,?,?,?,?)',
               (event_id,kind,forecast_id,canonical(payload),previous,digest(body)))
    return True

def records(path=None):
    with connect(path) as db:
        rows=db.execute('SELECT kind,forecast_id,payload FROM events ORDER BY seq').fetchall()
    forecasts={};outcomes={}
    for kind,key,payload in rows:
        (forecasts if kind=='forecast' else outcomes)[key]=json.loads(payload)
    return [dict(p,forecast_id=key,outcome=outcomes.get(key)) for key,p in forecasts.items()]

def record(ticker,t,s,provider,path=None,*,now=None):
    created=utc(now or datetime.now(timezone.utc));bar_date=pd.Timestamp(t['asof_bar_date']).date()
    age=(created.tz_convert(ET).date()-bar_date).days
    if age<0 or age>5: raise ValueError('Last completed daily bar is too old for a forward forecast.')
    if not math.isfinite(float(t['close'])) or t['close']<=0: raise ValueError('Invalid reference close.')
    reference=t.get('observation_reference') or {}
    ref_price=reference.get('price')
    ref_stamp=reference.get('bar_open_utc')
    if session_state(ticker,created)['market_open']:
        if ref_price is None or not ref_stamp or not 0 <= (created-utc(ref_stamp)).total_seconds() <= 900:
            raise ValueError('A recent timestamped reference price is required for an intraday forward observation.')
    base_close=float(ref_price) if ref_price is not None else float(t['close'])
    if not math.isfinite(base_close) or base_close<=0: raise ValueError('Invalid observation reference.')
    zone=s.get('entry_zone');targets=s.get('targets',[])
    features={k:v for k,v in t.items() if k not in ('daily','frames','structure','provenance','corporate_actions')}
    # Replace missing numeric feature values with explicit nulls, never zero.
    def scrub(v):
        if isinstance(v,dict): return {k:scrub(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)): return [scrub(x) for x in v]
        if isinstance(v,float) and not math.isfinite(v): return None
        return v
    added=[]
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        for horizon in (5,20):
            key=digest({'ticker':ticker,'source_date':str(bar_date),'horizon':horizon,'model':s.get('model_version',MODEL_VERSION)})
            future=schedule(ticker,created.tz_convert(ET).date()+pd.Timedelta(days=1),created.tz_convert(ET).date()+pd.Timedelta(days=60))
            maturity=future.index[horizon-1].date().isoformat()
            payload=scrub({'ticker':ticker,'exchange_calendar':t.get('provenance',{}).get('calendar'),
                'recorded_at_utc':created.isoformat(),'source_bar_date':str(bar_date),'provider':provider,
                'source_provenance':t.get('provenance',{}),'model_version':s.get('model_version',MODEL_VERSION),
                'features':features,'horizon_sessions':horizon,'maturity_date':maturity,
                'outcome_definition':'Unadjusted endpoint close vs frozen reference close on Nth exchange session AFTER recording date. Not executable P&L.',
                'base_close':base_close,'source_daily_close':t['close'],'reference_type':reference.get('kind','last completed daily close outside regular trading'),'reference_timestamp_utc':ref_stamp,
                'bias':s['bias'],'classification':s['classification'],'entry_zone':zone,'stop':s.get('stop'),'targets':targets,
                'ranges':s.get('ranges',{}).get(str(horizon),{}),
                'validation_kind':'forward_observation','policy':'UNVALIDATED','published_grade':None,
                'corporate_actions':t.get('corporate_actions',[])})
            if _append(db,'forecast',key,payload): added.append(key)
    return added

def resolve(ticker,daily,path=None,*,now=None,actions=None):
    now=utc(now or datetime.now(timezone.utc))
    rows=only_closed_daily(daily,now=now,symbol=ticker)
    if rows.empty: return 0
    rows=rows.copy();rows.index=rows.index.tz_convert(ET).tz_localize(None).normalize() if rows.index.tz is not None else rows.index.normalize()
    count=0
    for p in records(path):
        if p['ticker']!=ticker or p['outcome']: continue
        target=pd.Timestamp(p['maturity_date']);source=pd.Timestamp(p['source_bar_date'])
        if target not in rows.index: continue  # Missing target NEVER shifts maturity to a later available bar.
        known_revision=source in rows.index and not math.isclose(float(rows.loc[source,'Close']),p['source_daily_close'],rel_tol=1e-6,abs_tol=1e-6)
        action_risk=any(source.date()<pd.Timestamp(a['date']).date()<=target.date() and a.get('split',0) for a in (actions or []))
        actual=float(rows.loc[target,'Close']);bias=p['bias']
        invalid=known_revision or action_risk or source not in rows.index
        correct=None if invalid or bias not in ('UP','DOWN') else actual>p['base_close'] if bias=='UP' else actual<p['base_close']
        lo,hi=p['ranges'].get('lower'),p['ranges'].get('upper')
        outcome={'resolved_at_utc':now.isoformat(),'outcome_date':str(target.date()),'outcome_close':actual,
                 'status':'UNSCORABLE_REVISION' if invalid else 'RESOLVED',
                 'direction_correct':correct,'range_hit':None if invalid or lo is None or hi is None else lo<=actual<=hi,
                 'revision_check':'source revised, missing, or split reported' if invalid else 'source compared' if source in rows.index else 'source unavailable — endpoint only',
                 'scoring_version':'endpoint-v2','pnl':None,'target_before_stop':None}
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE')
            count+=int(_append(db,'outcome',p['forecast_id'],outcome))
    return count

def recent_records(path=None,limit=100):
    result=[]
    for p in records(path)[-limit:][::-1]:
        o=p['outcome'] or {}; band=p['ranges']
        result.append((p['ticker'],p['source_bar_date'],p['horizon_sessions'],p['bias'],p['classification'],p['base_close'],o.get('status','OPEN'),o.get('outcome_date'),o.get('outcome_close'),o.get('direction_correct'),band.get('lower'),band.get('upper')))
    return result

def audit_stats(path=None):
    data=records(path);stats={}
    for h in (5,20):
        group=[p for p in data if p['horizon_sessions']==h]
        if not group: continue
        outcomes=[p['outcome'] for p in group if p['outcome']]
        scored=[o for o in outcomes if o['direction_correct'] is not None]
        stats[h]={'total':len(group),'resolved':len(outcomes),'direction_wins':sum(o['direction_correct'] for o in scored),
                  'direction_evaluated':len(scored),'range_hits':sum(o['range_hit'] is True for o in outcomes),
                  'range_evaluated':sum(o['range_hit'] is not None for o in outcomes),
                  'validation_status':'INSUFFICIENT VALIDATION','tradable_performance':False}
    return stats

def export_events(path=None):
    with connect(path) as db:
        rows=db.execute('SELECT event_id,kind,forecast_id,payload,previous_hash,event_hash FROM events ORDER BY seq').fetchall()
    return [dict(event_id=e,kind=k,forecast_id=f,payload=json.loads(p),previous_hash=prev,event_hash=h) for e,k,f,p,prev,h in rows]

def verify_events(events):
    previous='0'*64; seen=set();forecasts=set()
    for event in events:
        body={k:v for k,v in event.items() if k!='event_hash'}
        if event['previous_hash']!=previous or digest(body)!=event['event_hash'] or event['event_id'] in seen:
            raise ValueError('Audit event chain failed integrity verification.')
        if event['kind']=='outcome' and event['forecast_id'] not in forecasts: raise ValueError('Orphan outcome')
        if event['kind']=='forecast': forecasts.add(event['forecast_id'])
        seen.add(event['event_id']);previous=event['event_hash']
    return True

def import_events(events,path=None):
    verify_events(events)
    existing=export_events(path)
    if events[:len(existing)]!=existing: raise ValueError('Audit history is not an append-only extension.')
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        for e in events[len(existing):]: _append(db,e['kind'],e['forecast_id'],e['payload'])
