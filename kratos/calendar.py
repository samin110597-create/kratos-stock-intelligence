"""US/TSX exchange sessions. UTC instants, Toronto display; no weekday guesses."""
from functools import lru_cache
import re
import pandas as pd
import pandas_market_calendars as mcal

ET = 'America/Toronto'

def calendar_name(symbol='SPY'):
    symbol = symbol.upper()
    if symbol.endswith(('.TO', '.V')):
        return 'TSX'
    if re.fullmatch(r'[A-Z][A-Z0-9-]{0,14}', symbol) or symbol in ('^GSPC', '^IXIC', '^DJI', '^VIX'):
        return 'NYSE'
    raise ValueError('Exchange calendar unsupported; use a US equity symbol or TSX .TO symbol.')

@lru_cache(maxsize=128)
def _schedule(name, start, end):
    return mcal.get_calendar(name).schedule(start_date=start, end_date=end)

def schedule(symbol, start, end):
    return _schedule(calendar_name(symbol), str(pd.Timestamp(start).date()), str(pd.Timestamp(end).date())).copy()

def utc(value):
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError('An explicit timezone is required for an as-of instant.')
    return stamp.tz_convert('UTC')

def session_state(symbol, now):
    now = utc(now)
    day = now.tz_convert(ET).date()
    try:
        sched = schedule(symbol, day, day)
    except ValueError:
        return {'state':'UNKNOWN', 'market_open':False, 'calendar':None}
    if sched.empty:
        return {'state':'CLOSED', 'market_open':False, 'calendar':calendar_name(symbol)}
    row = sched.iloc[0]
    opened = row.market_open <= now < row.market_close
    return {'state':'REGULAR' if opened else 'PREMARKET' if now < row.market_open else 'AFTER_HOURS',
            'market_open':bool(opened), 'calendar':calendar_name(symbol),
            'open_utc':row.market_open.isoformat(), 'close_utc':row.market_close.isoformat(),
            'halt_status':'UNKNOWN — calendar cannot detect trading halts'}

def bar_bounds(index, symbol='SPY', interval='1d'):
    if len(index)==0:
        return []
    local = index.tz_convert(ET) if index.tz is not None else index
    sched = schedule(symbol, local.min().date(), local.max().date())
    result=[]
    for stamp, label in zip(index, local):
        day = pd.Timestamp(label.date())
        if day not in sched.index:
            result.append(None); continue
        row=sched.loc[day]
        if interval=='1d':
            result.append((row.market_open, row.market_close)); continue
        if stamp.tzinfo is None:
            result.append(None); continue
        start=stamp.tz_convert('UTC')
        if not row.market_open <= start < row.market_close:
            result.append(None); continue
        step=pd.Timedelta(interval)
        if (start-row.market_open) % step != pd.Timedelta(0):
            result.append(None); continue
        result.append((start,min(start+step,row.market_close)))
    return result

def closed_bars(frame, interval, now, symbol='SPY'):
    if frame.empty: return frame.copy()
    cutoff=utc(now)
    bounds=bar_bounds(frame.index,symbol,interval)
    return frame.loc[[b is not None and b[1] <= cutoff for b in bounds]].copy()

def aggregate_intraday(frame, minutes, source_minutes, now, symbol='SPY'):
    """Session-anchored bars, including shortened final bars; require every input."""
    if frame.empty: return frame.copy()
    frame=closed_bars(frame,f'{source_minutes}min',now,symbol)
    if frame.empty: return frame
    local=frame.index.tz_convert(ET)
    sched=schedule(symbol,local.min().date(),local.max().date())
    rows=[]; labels=[]
    for _, session in sched.iterrows():
        start=session.market_open
        while start < session.market_close:
            end=min(start+pd.Timedelta(minutes=minutes),session.market_close)
            expected=pd.date_range(start,end,freq=f'{source_minutes}min',inclusive='left')
            if end <= utc(now) and expected.isin(frame.index).all():
                chunk=frame.loc[expected]
                rows.append({'Open':chunk.Open.iloc[0],'High':chunk.High.max(),'Low':chunk.Low.min(),
                             'Close':chunk.Close.iloc[-1],
                             'Volume':chunk.Volume.sum() if chunk.Volume.notna().all() else float('nan')})
                labels.append(start)
            start=end
    return pd.DataFrame(rows,index=pd.DatetimeIndex(labels,tz='UTC'),columns=frame.columns[:5])

def weekly_closed(frame, now, symbol='SPY'):
    if frame.empty: return frame.copy()
    cutoff=utc(now); keep=[]
    local=frame.index.tz_convert(ET) if frame.index.tz is not None else frame.index
    fridays=pd.DatetimeIndex([pd.Timestamp(stamp.date()) for stamp in local])
    sessions=schedule(symbol,fridays.min()-pd.Timedelta(days=4),fridays.max())
    for friday in fridays:
        sched=sessions.loc[friday-pd.Timedelta(days=4):friday]
        keep.append(not sched.empty and sched.iloc[-1].market_close <= cutoff)
    return frame.loc[keep].copy()
