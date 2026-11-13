"""Exchange-calendar freshness and plain-English, completed-candle assessments."""
from datetime import datetime, timezone
import hashlib
import json
import pandas as pd
from .calendar import schedule, bar_bounds, utc, ET
from .technicals import indicators, finite, trend_label
from .price_plan import describe

TIMEFRAMES = {'1H':60, '4H':240, '1D':None, '1W':None}


def expected_closes(symbol, now):
    now=utc(now)
    sessions=schedule(symbol, now.tz_convert(ET).date()-pd.Timedelta(days=24),
                      now.tz_convert(ET).date()+pd.Timedelta(days=7))
    out={tf:[] for tf in TIMEFRAMES}
    for day,row in sessions.iterrows():
        if row.market_close<=now: out['1D'].append(row.market_close)
        for tf,minutes in [('1H',60),('4H',240)]:
            start=row.market_open
            while start<row.market_close:
                end=min(start+pd.Timedelta(minutes=minutes),row.market_close)
                if end<=now: out[tf].append(end)
                start=end
    for _,week in sessions.groupby(sessions.index.to_period('W-FRI')):
        end=week.iloc[-1].market_close
        # The query includes next week, so current-week holidays are known.
        if end<=now: out['1W'].append(end)
    return {tf:max(values) if values else None for tf,values in out.items()}


def actual_close(frame, tf, symbol):
    if frame is None or frame.empty:return None
    if tf=='1W':
        label=pd.Timestamp(frame.index[-1]).tz_localize(None).normalize()
        week=schedule(symbol,label-pd.Timedelta(days=4),label)
        return week.iloc[-1].market_close if not week.empty else None
    bounds=bar_bounds(frame.index[-1:],symbol,'1d' if tf=='1D' else f'{TIMEFRAMES[tf]}min')
    return bounds[0][1] if bounds and bounds[0] else None


def build_timeframe_report(snapshot, frames, now=None):
    now=utc(now or datetime.now(timezone.utc))
    expected=expected_closes(snapshot.ticker,now)
    rows={}
    for tf in TIMEFRAMES:
        frame=frames.get(tf)
        ended=actual_close(frame,tf,snapshot.ticker)
        current=ended is not None and expected[tf] is not None and ended==expected[tf] and ended<=now
        summary=describe(frame)
        ready=current and summary['state']!='UNAVAILABLE'
        trend=trend_label(frame) if ready else 'UNAVAILABLE'
        metrics=indicators(frame).iloc[-1] if ready else None
        rows[tf]={'trend':trend,'structure':summary['state'] if ready else 'UNAVAILABLE',
            'freshness':'LATEST_COMPLETED' if current else 'STALE_OR_MISSING',
            'bar_closed_at_utc':ended.isoformat() if ended is not None else None,
            'expected_close_utc':expected[tf].isoformat() if expected[tf] is not None else None,
            'explanation':summary['explanation'] if ready else 'Latest completed candle missing or insufficient history. No current trend issued.',
            'rsi':float(metrics.RSI14) if ready and finite(metrics.RSI14) else None,
            'volume_ratio':summary.get('volume_ratio') if ready else None,
            'support':summary.get('support',[]) if ready else [],
            'resistance':summary.get('resistance',[]) if ready else [],
            'source':snapshot.provider,'retrieved_at_utc':snapshot.retrieved_at.isoformat()}
    trends=[r['trend'] for r in rows.values()]
    if 'UNAVAILABLE' in trends or 'UNKNOWN' in trends:
        verdict='INCOMPLETE DATA'; message='At least one timeframe lacks current completed candles or enough history. A combined direction is unavailable.'
    elif all(t=='UP' for t in trends):
        verdict='UPWARD ALIGNMENT';message='All four moving-average trends point up. Check the nearest resistance before considering an entry; this does not predict a guaranteed rise.'
    elif all(t=='DOWN' for t in trends):
        verdict='DOWNWARD ALIGNMENT';message='All four moving-average trends point down. A low price or oversold RSI alone is not a confirmed reversal.'
    else:
        verdict='MIXED TIMEFRAMES';message='The timeframes disagree or are ranging. An intraday bounce can still occur inside a weaker daily or weekly trend.'
    return {'checked_at_utc':now.isoformat(),'timeframes':rows,'verdict':verdict,'summary':message,
        'method':'Trend: completed close above EMA20 above EMA50 = UP; reverse = DOWN; otherwise MIXED. Structure uses confirmed swings separately.',
        'session_basis':'Regular exchange sessions; 4H anchored to 09:30 ET, final session bucket can be shorter. Weekly uses the last fully completed exchange week.'}


def data_version(snapshot):
    """Stable if underlying observations are unchanged, regardless of receipt time."""
    payload={'source':snapshot.provider,'fundamentals':snapshot.fundamentals}
    for name in ('daily','hourly','quarter','minute'):
        frame=getattr(snapshot,name)
        payload[name]=frame.to_json(date_format='iso',double_precision=12)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
