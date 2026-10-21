"""Opt-in personal research connectors. Never copy raw responses to public Pages.

SQLite budgets persist across workers/restarts on the same durable filesystem.
Conservative local limits are not a statement of account entitlements. No upgrades,
paid-feed fallback, arbitrary URLs, or credentials in returned errors.
"""
from datetime import datetime, timezone, date
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import httpx

CONFIG = {
 'twelve_data': ('TWELVE_DATA_API_KEY', 8, 800, 'https://api.twelvedata.com/time_series'),
 'fmp': ('FMP_API_KEY', 5, 250, 'https://financialmodelingprep.com/stable/profile'),
 'finnhub': ('FINNHUB_API_KEY', 30, 500, 'https://finnhub.io/api/v1/quote'),
 'fred': ('FRED_API_KEY', 10, 100, 'https://api.stlouisfed.org/fred/series/observations'),
 'massive': ('MASSIVE_API_KEY', 5, 100, 'https://api.massive.com/v2/aggs/ticker/{symbol}/prev'),
 'alpha_vantage': ('ALPHA_VANTAGE_API_KEY', 5, 25, 'https://www.alphavantage.co/query'),
 'alpaca': ('ALPACA_API_KEY', 10, 100, 'https://data.alpaca.markets/v1beta1/options/snapshots/{symbol}'),
}
ALIASES={'massive':'POLYGON_API_KEY','alpha_vantage':'ALPHAVANTAGE_API_KEY','twelve_data':'TWELVEDATA_API_KEY'}
class ConnectorError(ValueError): pass

def key_for(name):
    return os.getenv(CONFIG[name][0]) or os.getenv(ALIASES.get(name,''),'')

def status():
    return {name:{'configured':bool(key_for(name)) and (name!='alpaca' or bool(os.getenv('ALPACA_SECRET_KEY'))),
                  'public_redistribution_enabled':False,'minute_budget':cfg[1],'daily_budget':cfg[2],
                  'entitlement':'Unverified until account request succeeds'} for name,cfg in CONFIG.items()}

class Connectors:
    def __init__(self, path=None, client=None, clock=time.time):
        self.path=str(path or Path(os.getenv('KRATOS_DB_DIR','data'))/'connector-budget.sqlite3')
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        self.client=client or httpx.Client(timeout=20,follow_redirects=False)
        self.clock=clock
        with self.db() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS calls(provider TEXT,t REAL); CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY,t REAL,payload TEXT);')
    def db(self): return sqlite3.connect(self.path,timeout=10)
    def fetch(self,name,symbol='NVDA',*,vintage=None,page_token=None):
        if name not in CONFIG: raise ConnectorError('Unknown connector')
        if not re.fullmatch(r'[A-Za-z0-9.^_-]{1,24}',symbol): raise ConnectorError('Invalid symbol or series')
        if not key_for(name): raise ConnectorError(name+': credential not configured')
        if name=='alpaca' and not os.getenv('ALPACA_SECRET_KEY'): raise ConnectorError('alpaca: secret not configured')
        if vintage: date.fromisoformat(vintage)
        cachekey=hashlib.sha256(json.dumps([name,symbol,vintage,page_token]).encode()).hexdigest()
        now=self.clock(); minute,daily=CONFIG[name][1:3]
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT t,payload FROM cache WHERE k=?',(cachekey,)).fetchone()
            if row and 0<=now-row[0]<900: return json.loads(row[1])
            db.execute('DELETE FROM calls WHERE t<?',(now-86400,))
            counts=[db.execute('SELECT count(*) FROM calls WHERE provider=? AND t>?',(name,now-window)).fetchone()[0] for window in (60,86400)]
            if counts[0]>=minute or counts[1]>=daily: raise ConnectorError(name+': local request budget exhausted')
            db.execute('INSERT INTO calls VALUES(?,?)',(name,now))
        params={}; headers={}; key=key_for(name)
        if name=='twelve_data': params={'symbol':symbol,'interval':'1day','outputsize':100,'apikey':key}
        elif name=='fmp': params={'symbol':symbol,'apikey':key}
        elif name=='finnhub': params={'symbol':symbol}; headers={'X-Finnhub-Token':key}
        elif name=='fred':
            params={'series_id':symbol,'api_key':key,'file_type':'json','sort_order':'desc','limit':100}
            if vintage: params.update(realtime_start=vintage,realtime_end=vintage)
        elif name=='massive': params={'adjusted':'false'}; headers={'Authorization':'Bearer '+key}
        elif name=='alpha_vantage': params={'function':'TIME_SERIES_DAILY','symbol':symbol,'outputsize':'compact','apikey':key}
        elif name=='alpaca':
            params={'feed':'indicative','limit':100}
            if page_token: params['page_token']=page_token
            headers={'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':os.environ['ALPACA_SECRET_KEY']}
        try:
            response=self.client.get(CONFIG[name][3].format(symbol=symbol),params=params,headers=headers)
            if response.status_code!=200: raise ConnectorError(f'{name}: HTTP {response.status_code}; no data substituted')
            payload=response.json()
        except ConnectorError: raise
        except Exception: raise ConnectorError(name+': transport/response failure') from None
        if not payload or (isinstance(payload,dict) and any(k in payload for k in ('Error Message','Information','Note','error','error_message'))):
            raise ConnectorError(name+': unavailable, rate-limited or not entitled')
        validate_payload(name,payload)
        result={'provider':name,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                'source_timestamp':None,'source_timestamp_status':'Use native timestamps in payload; retrieval is not event time',
                'public_redistribution_enabled':False,'vintage_requested':vintage,'payload':payload,
                'limitations': 'Personal research only; account permissions and data coverage apply.'}
        if name=='finnhub':
            t=payload.get('t'); result['source_timestamp']=datetime.fromtimestamp(t,timezone.utc).isoformat() if isinstance(t,(int,float)) and t>0 else None
        if name=='twelve_data': result['limitations']='Basic plan internal non-display terms; raw data must not be exposed in dashboard without verified display rights.'
        if name=='alpaca': result['limitations']='Indicative modified quotes and derivative trades delayed 15 minutes; not OPRA, OI not supplied by snapshots. Pagination may be incomplete.'
        if name=='massive': result['limitations']='Previous completed daily aggregate, not a current quote; unadjusted requested.'
        if name=='alpha_vantage': result['limitations']='Compact daily history, not an intraday/live source.'
        if name=='fred': result['limitations']='Observation date is not publication time; requested ALFRED vintage is date-level, not intraday availability.'
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(cachekey,now,json.dumps(result,allow_nan=False)))
        return result


def validate_payload(name,payload):
    import math
    valid=False
    if name=='fmp': valid=isinstance(payload,list) and bool(payload) and isinstance(payload[0],dict) and bool(payload[0].get('symbol'))
    elif name=='finnhub': valid=isinstance(payload,dict) and isinstance(payload.get('c'),(float,int)) and math.isfinite(payload['c']) and payload['c']>0 and isinstance(payload.get('t'),(float,int)) and 0<payload['t']<=time.time()+120
    elif name=='fred': valid=isinstance(payload,dict) and isinstance(payload.get('observations'),list)
    elif name=='massive': valid=isinstance(payload,dict) and bool(payload.get('results')) and payload.get('status') in ('OK','DELAYED')
    elif name=='alpha_vantage': valid=isinstance(payload,dict) and bool(payload.get('Time Series (Daily)'))
    elif name=='alpaca': valid=isinstance(payload,dict) and isinstance(payload.get('snapshots'),dict) and bool(payload['snapshots'])
    elif name=='twelve_data': valid=isinstance(payload,dict) and payload.get('status')=='ok' and bool(payload.get('values'))
    if not valid: raise ConnectorError(name+': empty or unexpected data schema; no observation fabricated')
