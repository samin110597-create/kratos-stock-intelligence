"""Source-aware ingress. Invalid bars fail closed; no invented market observations."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from typing import Protocol
import re
import time
import pandas as pd
import numpy as np
from .calendar import session_state, calendar_name, bar_bounds

ET = ZoneInfo('America/Toronto')
_SYMBOL = re.compile(r'^[A-Z0-9^][A-Z0-9.^=_-]{0,19}$')
class MarketDataError(RuntimeError): pass

def valid_symbol(symbol):
    ticker=str(symbol).strip().upper()
    if ticker.startswith('TSX:'): ticker=ticker[4:]+'.TO'
    if ticker.startswith(('NYSE:','NASDAQ:')): ticker=ticker.split(':')[1]
    if not _SYMBOL.fullmatch(ticker):
        raise ValueError('Enter a valid ticker, e.g. NVDA, CIFR, BRK-B or RY.TO.')
    return ticker

def tidy(frame):
    fields=['Open','High','Low','Close','Volume']
    if frame is None or frame.empty: return pd.DataFrame(columns=fields)
    frame=frame.copy()
    if isinstance(frame.columns,pd.MultiIndex): frame.columns=frame.columns.get_level_values(0)
    if not isinstance(frame.index,pd.DatetimeIndex) or frame.index.hasnans:
        raise MarketDataError('Price bars have no valid datetime index.')
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise MarketDataError('Duplicate or non-monotonic bar timestamps; data rejected.')
    if not all(c in frame.columns for c in fields):
        raise MarketDataError('Price data is missing an OHLCV field.')
    frame=frame[fields].apply(pd.to_numeric,errors='coerce')
    ohlc=frame[fields[:4]]
    if not np.isfinite(ohlc.to_numpy()).all() or (ohlc<=0).any().any():
        raise MarketDataError('Missing, non-finite or nonpositive OHLC prices.')
    if ((frame.High < ohlc.max(axis=1)) | (frame.Low > ohlc.min(axis=1))).any():
        raise MarketDataError('Impossible OHLC bounds; data rejected.')
    if ((frame.Volume.dropna()<0) | ~np.isfinite(frame.Volume.dropna())).any():
        raise MarketDataError('Invalid volume; data rejected.')
    return frame

def is_regular_session(now,symbol):
    return session_state(symbol,now)['market_open']

@dataclass
class MarketSnapshot:
    ticker: str
    daily: pd.DataFrame
    hourly: pd.DataFrame
    minute: pd.DataFrame
    fundamentals: dict
    provider: str
    retrieved_at: datetime
    warnings: list[str]
    quarter: pd.DataFrame = field(default_factory=pd.DataFrame)
    provenance: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    quote: dict = field(default_factory=dict)

    def freshness(self,at=None):
        now=at or datetime.now(timezone.utc)
        session=session_state(self.ticker,now)
        result={'market_open_estimate':session['market_open'],'session':session,'age_minutes':None,
                'live_enough':False,'last_bar':None, 'entitlement':'UNVERIFIED',
                'status':'INTRADAY UNAVAILABLE — daily research only'}
        if self.minute.empty: return result
        stamp=self.minute.index[-1]
        if stamp.tzinfo is None:
            result['status']='UNVERIFIED timestamp timezone'; return result
        age=(pd.Timestamp(now)-stamp.tz_convert('UTC')).total_seconds()/60
        if age < 0:
            result['status']='FUTURE BAR TIMESTAMP — clock/provider mismatch';return result
        bounds=bar_bounds(self.minute.tail(1).index,self.ticker,'1min')
        if not bounds[0]:
            result['status']='INVALID EXCHANGE SESSION — no live trade signal';return result
        result.update(age_minutes=round(age,1),last_bar=stamp.tz_convert(ET).strftime('%Y-%m-%d %I:%M %p %Z'))
        result['live_enough']=session['market_open'] and age<=15
        result['status']=('RECENT reported minute bar; entitlement unverified' if result['live_enough'] else
                          'STALE DATA — NO VALIDATED LIVE TRADE SIGNAL' if session['market_open'] else
                          'MARKET CLOSED — last reported minute bar; no live entry')
        return result

class Provider(Protocol):
    name: str
    def fetch(self,ticker: str) -> MarketSnapshot: ...

class YahooProvider:
    name='Yahoo Finance (unofficial yfinance feed)'
    def fetch(self,ticker):
        import yfinance as yf
        client=yf.Ticker(ticker); warnings=[]; receipts={}; actions=[]
        def history(period,interval,required=False):
            for attempt in range(2):
                try:
                    raw=client.history(period=period,interval=interval,auto_adjust=False,
                                       prepost=False,actions=True,timeout=12)
                    frame=tidy(raw)
                    if frame.empty: raise MarketDataError('Provider returned no bars.')
                    if interval=='1d':
                        for idx,row in raw.iterrows():
                            split=float(row.get('Stock Splits',0) or 0)
                            dividend=float(row.get('Dividends',0) or 0)
                            if split or dividend: actions.append({'date':str(idx.date()),'split':split,'dividend':dividend})
                    receipts[interval]=datetime.now(timezone.utc).isoformat()
                    return frame
                except Exception as exc:
                    if attempt==0 and not isinstance(exc,MarketDataError):
                        time.sleep(.25);continue
                    if required: raise MarketDataError(f'{interval} market history unavailable or invalid ({type(exc).__name__}).') from exc
                    warnings.append(f'{interval} unavailable or rejected ({type(exc).__name__}).')
                    return tidy(None)
        daily=history('3y','1d',True)
        hourly=history('60d','60m'); quarter=history('60d','15m'); minute=history('5d','1m')
        try: facts=client.get_info() or {}
        except Exception:
            facts={};warnings.append('Fundamental metadata unavailable.')
        if daily.Volume.isna().any(): warnings.append('Missing volume: affected volume features unavailable.')
        if (daily.Close.pct_change().abs()>.45).any():
            warnings.append('Large historical discontinuity: inspect corporate actions; raw-price returns can be distorted.')
        warnings += ['Yahoo is unofficial; no uptime, <=15-minute delay or redistribution entitlement guaranteed.',
                     'Unadjusted OHLC requested. Provider may retrospectively split-normalize historical prices; dividends excluded. Not point-in-time history.',
                     'Fundamentals are current provider metadata, not publication-dated filings; excluded from backtests.']
        quote={}
        if not minute.empty:
            quote={'price':float(minute.Close.iloc[-1]), 'bar_open_utc':minute.index[-1].tz_convert('UTC').isoformat(),
                   'event_timestamp_utc':None,'kind':'Latest reported 1-minute bar close, potentially developing; not a live quote',
                   'source':self.name}
        return MarketSnapshot(ticker,daily,hourly,minute,facts,self.name,datetime.now(timezone.utc),warnings,
                              quarter=quarter,actions=actions,quote=quote,
                              provenance={'bar_receipt_times_utc':receipts,'provider_timestamp_utc':None,
                                          'event_timestamp_utc':None,'reported_delay_minutes':None,
                                          'entitlement':'UNVERIFIED','price_adjustment':'auto_adjust=False; provider revisions possible',
                                          'calendar':calendar_name(ticker),
                                          'currency':facts.get('currency'), 'exchange':facts.get('exchange')})

class ProviderRouter:
    """Explicit priority, bounded cache, health counters; fallback source always disclosed."""
    def __init__(self,providers=None,ttl_seconds=60,capacity=64):
        self.providers=providers or [YahooProvider()];self.ttl=ttl_seconds;self.capacity=capacity
        self.cache=OrderedDict(); self.health={};self.lock=Lock()
    def fetch(self,ticker):
        ticker=valid_symbol(ticker);calendar_name(ticker)
        # Serialize upstream calls to prevent concurrent cache misses exhausting a free feed.
        with self.lock:
            cached=self.cache.get(ticker)
            if cached and time.monotonic()-cached[0]<self.ttl:
                self.cache.move_to_end(ticker);return deepcopy(cached[1])
            failures=[]
            for provider in self.providers:
                start=time.monotonic()
                try:
                    snap=provider.fetch(ticker)
                    snap.warnings=failures+snap.warnings
                    self.health[provider.name]={'ok':True,'latency_seconds':round(time.monotonic()-start,3),
                                                'checked_at_utc':datetime.now(timezone.utc).isoformat()}
                    self.cache[ticker]=(time.monotonic(),deepcopy(snap))
                    while len(self.cache)>self.capacity: self.cache.popitem(last=False)
                    return snap
                except Exception as exc:
                    self.health[provider.name]={'ok':False,'error_type':type(exc).__name__}
                    failures.append(f'{provider.name} unavailable ({type(exc).__name__}); fallback attempted.')
            raise MarketDataError('All configured sources unavailable or invalid. No signal generated. '+ ' '.join(failures))

def configured_providers():
    import os
    from .account_provider import AlphaDailyProvider
    from .connectors import key_for
    # A compact daily account feed cannot provide intraday coverage. Selection is explicit.
    order=os.getenv('KRATOS_PROVIDER_ORDER','yahoo').split(',')
    factories={'yahoo':YahooProvider,'alpha_vantage':AlphaDailyProvider}
    if any(name.strip() not in factories for name in order): raise ValueError('Unsupported market-history provider')
    return [factories[name.strip()]() for name in order]

ROUTER=ProviderRouter(configured_providers())
def fetch_snapshot(ticker): return ROUTER.fetch(ticker)
