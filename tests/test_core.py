"""Synthetic bars are TEST FIXTURES ONLY; never surfaced as market quotes."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import math
import numpy as np
import pandas as pd
import pytest

from kratos.data import tidy, valid_symbol, MarketSnapshot
from kratos.technicals import (indicators, only_closed_daily, only_closed_weekly,
                               build_technicals, resample_ohlcv)
from kratos.decision import propose_setup
from kratos.fundamentals import report
from kratos.engine import analyze


def bars(count=360, step=0.12, freq='B', end=None):
    end=end or pd.Timestamp.now(tz='America/Toronto').normalize() - pd.Timedelta(days=4)
    idx=pd.date_range(end=end, periods=count, freq=freq, tz='America/Toronto')
    c = np.asarray([50 + i * step for i in range(count)],float)
    return pd.DataFrame({'Open':c-.2,'High':c+.9,'Low':c-1.,'Close':c,
                         'Volume':np.ones(count)*1_000_000},index=idx)


def test_symbol_validation():
    assert valid_symbol('ry.to')=='RY.TO'
    assert valid_symbol('BRK-B')=='BRK-B'
    with pytest.raises(ValueError):valid_symbol('NVDA; rm -rf /')


def test_indicators_use_history_only():
    prices=bars()
    old = indicators(prices.iloc[:-1])
    now = indicators(prices)
    assert old.iloc[-1]['EMA20'] == pytest.approx(now.iloc[-2]['EMA20'])
    assert old.iloc[-1]['ATR14'] == pytest.approx(now.iloc[-2]['ATR14'])
    assert 0 <= now.iloc[-1]['RSI14'] <= 100


def test_price_change_after_bar_does_not_change_past_signal():
    prices=bars()
    a=indicators(prices.iloc[:220]).iloc[-1]
    changed=prices.copy()
    changed.loc[changed.index[221]:, 'Close']=100000
    b=indicators(changed.iloc[:220]).iloc[-1]
    assert a['EMA20']==b['EMA20']
    assert a['RSI14']==b['RSI14']


def test_drop_unfinished_daily():
    t=ZoneInfo('America/Toronto')
    current=datetime(2026,10,19,11,0,tzinfo=t)
    idx=pd.date_range('2026-10-15',periods=3,freq='B',tz=t)
    f=pd.DataFrame({'Close':[1,2,3]},index=idx)
    assert len(only_closed_daily(f,now=current))==2
    assert len(only_closed_daily(f,now=datetime(2026,10,19,17,tzinfo=t)))==3


def test_weekly_partial_is_dropped():
    t=ZoneInfo('America/Toronto')
    weekly=pd.DataFrame({'Close':[2,3]},index=pd.DatetimeIndex(['2026-10-16','2026-10-23']))
    assert len(only_closed_weekly(weekly,now=datetime(2026,10,19,13,tzinfo=t)))==1
    assert len(only_closed_weekly(weekly,now=datetime(2026,10,24,13,tzinfo=t)))==2


def test_no_buy_when_data_stale():
    prices=bars()
    tech=build_technicals(prices,pd.DataFrame())
    dec=propose_setup(tech,{'live_enough':False})
    assert dec['classification']!='BUY SETUP'


def test_no_claimed_intrinsic_for_no_eps():
    facts,note=report({'sector':'Technology','forwardEps':-2})
    assert 'no fair value' in note.lower()
    _,note2=report({'sector':'Financial Services','forwardEps':2})
    assert 'omitted' in note2


def test_snapshot_missing_intraday_blocks_buy():
    prices=bars()
    snapshot=MarketSnapshot('TEST',prices,pd.DataFrame(),pd.DataFrame(),{},
                            'fixture',datetime.now(timezone.utc),[])
    result=analyze('TEST',snapshot=snapshot)
    assert not result.freshness['live_enough']
    assert result.decision['classification'] !='BUY SETUP'


def test_projections_not_probabilities():
    tech={'close':100.,'atr':2.,'ema20':99.5,'rsi':55.,
          'trends':{'1D':'UP','1W':'UP','1H':'UP'},
          'support20':96.,'resistance60':140.,'volume_ratio':1.1}
    s=propose_setup(tech,{'live_enough':True})
    assert s['classification']=='WAIT'
    assert 'INSUFFICIENT VALIDATION' in s['grade']
    assert s['ranges']['20']['upper'] == pytest.approx(100+2*math.sqrt(20))
    assert s['targets'][1]>s['targets'][0]>s['entry_zone'][0]


def test_freshness_stale_even_if_regular_session():
    t=ZoneInfo('America/Toronto')
    now=datetime(2026,10,19,11,0,tzinfo=t)
    older=pd.date_range('2026-10-19 10:30',periods=1,tz=t)
    minute=pd.DataFrame({'Open':[10],'High':[10],'Low':[10],
                         'Close':[10],'Volume':[200]},index=older)
    snap=MarketSnapshot('NVDA',bars(),pd.DataFrame(),minute,{},'fixture',now,[])
    status=snap.freshness(at=now)
    assert status['age_minutes']==30
    assert not status['live_enough']


def test_future_minute_timestamp_never_claims_live():
    t = ZoneInfo('America/Toronto')
    now = datetime(2026,10,19,11,0,tzinfo=t)
    ahead = pd.date_range('2026-10-19 11:10',periods=1,tz=t)
    minute = pd.DataFrame({'Open':[10], 'High':[10], 'Low':[10],
                           'Close':[10], 'Volume':[100]},index=ahead)
    snap = MarketSnapshot('NVDA',bars(),pd.DataFrame(),minute,{},'fixture',now,[])
    assert not snap.freshness(at=now)['live_enough']
    assert 'FUTURE' in snap.freshness(at=now)['status']
