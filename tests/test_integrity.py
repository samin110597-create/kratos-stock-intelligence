"""Regression fixtures: synthetic, never used as market observations."""
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest
from kratos.data import tidy, MarketDataError, is_regular_session
from kratos.technicals import indicators, only_closed_daily, only_closed_hourly, only_closed_weekly, resample_ohlcv
ET=ZoneInfo('America/Toronto')
def bars(index, close=100.):
    return pd.DataFrame({'Open':close,'High':close+1,'Low':close-1,'Close':close,'Volume':100.}, index=index)
def test_flat_rsi_is_neutral_and_warmup_is_missing():
    r=indicators(bars(pd.date_range('2026-01-01', periods=40)))['RSI14']
    assert r.iloc[-1] == 50
    assert r.iloc[:14].isna().all()
def test_reject_duplicate_bars():
    with pytest.raises(MarketDataError): tidy(bars(pd.DatetimeIndex(['2026-01-02']*2)))
def test_reject_unsorted_bars():
    with pytest.raises(MarketDataError): tidy(bars(pd.DatetimeIndex(['2026-01-03','2026-01-02'])))
def test_reject_impossible_ohlc():
    f=bars(pd.date_range('2026-01-01', periods=2));f.iloc[0,f.columns.get_loc('High')]=90
    with pytest.raises(MarketDataError): tidy(f)
def test_nyse_holiday_closed():
    assert not is_regular_session(datetime(2026,12,25,11,tzinfo=ET),'NVDA')
def test_tsx_thanksgiving_closed_but_us_open():
    now=datetime(2026,10,12,11,tzinfo=ET)
    assert not is_regular_session(now,'RY.TO')
    assert is_regular_session(now,'NVDA')
def test_half_day_daily_final_at_actual_close():
    f=bars(pd.DatetimeIndex(['2026-11-27'],tz=ET))
    assert len(only_closed_daily(f,now=datetime(2026,11,27,13,2,tzinfo=ET)))==1
def test_future_daily_rows_removed():
    f=bars(pd.DatetimeIndex(['2026-10-19','2026-10-20'],tz=ET))
    assert only_closed_daily(f,now=datetime(2026,10,19,11,tzinfo=ET)).empty
def test_last_short_hour_is_closed_at_session_close():
    f=bars(pd.DatetimeIndex(['2026-10-19 15:30'],tz=ET))
    assert len(only_closed_hourly(f,now=datetime(2026,10,19,16,2,tzinfo=ET)))==1
def test_good_friday_week_complete_thursday():
    f=bars(pd.DatetimeIndex(['2026-04-03']))
    assert len(only_closed_weekly(f,now=datetime(2026,4,2,16,2,tzinfo=ET)))==1
def test_missing_volume_not_summed_to_zero():
    f=bars(pd.date_range('2026-01-05',periods=5)); f['Volume']=np.nan
    assert resample_ohlcv(f,'W-FRI')['Volume'].isna().all()

def test_four_hour_aggregate_requires_full_bucket():
    from kratos.calendar import aggregate_intraday
    f=bars(pd.date_range('2026-10-19 09:30',periods=7,freq='h',tz=ET))
    assert aggregate_intraday(f,240,60,datetime(2026,10,19,12,30,tzinfo=ET)).empty
    assert len(aggregate_intraday(f,240,60,datetime(2026,10,19,13,30,tzinfo=ET)))==1
    assert len(aggregate_intraday(f,240,60,datetime(2026,10,19,16,tzinfo=ET)))==2
    assert aggregate_intraday(f.drop(f.index[1]),240,60,datetime(2026,10,19,13,30,tzinfo=ET)).empty

def test_dst_uses_exchange_local_time():
    assert is_regular_session(datetime(2026,11,2,14,30,tzinfo=ZoneInfo('UTC')),'NVDA')
    assert not is_regular_session(datetime(2026,11,2,13,30,tzinfo=ZoneInfo('UTC')),'NVDA')

def test_pivots_do_not_confirm_before_right_bars_exist():
    from kratos.patterns import inspect
    f=bars(pd.date_range('2026-01-01',periods=30))
    f.iloc[-2,f.columns.get_loc('High')]=200
    assert not inspect(f)['confirmed_highs']

def test_etf_never_receives_company_pe_valuation():
    from kratos.fundamentals import report
    assert 'Stock-style intrinsic value omitted' in report({'quoteType':'ETF','forwardEps':5})[1]


def test_bos_history_is_causal_under_future_append():
    from kratos.patterns import causal_breaks
    rng=np.random.default_rng(21);n=120;c=100+np.cumsum(rng.normal(0,2,n))
    f=pd.DataFrame({'Open':c,'High':c+1,'Low':c-1,'Close':c,'Volume':100},index=pd.date_range('2026-01-01',periods=n))
    early=causal_breaks(f.iloc[:80]);all_events=causal_breaks(f)
    assert early==[x for x in all_events if x['bar']<=f.index[79].isoformat()]


def test_session_vwap_resets_at_trading_date():
    from kratos.patterns import session_vwap
    f=bars(pd.DatetimeIndex(['2026-10-19 15:30','2026-10-20 09:30','2026-10-20 10:30'],tz=ET))
    expected=float((((f.High+f.Low+f.Close)/3)*f.Volume).iloc[1:].sum()/f.Volume.iloc[1:].sum())
    # Function detects session spacing from minimum step, not overnight gap.
    assert session_vwap(f)==expected
