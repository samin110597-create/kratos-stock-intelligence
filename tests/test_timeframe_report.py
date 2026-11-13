import pandas as pd
from types import SimpleNamespace
from kratos.timeframe_report import expected_closes, actual_close, build_timeframe_report, data_version


def candles(index):
    return pd.DataFrame({'Open':100.,'High':101.,'Low':99.,'Close':100.,'Volume':1000.},index=index)


def test_partial_hour_and_four_hour_candles_are_not_expected():
    result=expected_closes('NVDA','2026-11-12T17:15:00Z')
    assert result['1H']==pd.Timestamp('2026-11-12T16:30Z')
    assert result['4H']==pd.Timestamp('2026-11-11T21:00Z')
    assert result['1D']==pd.Timestamp('2026-11-11T21:00Z')
    assert result['1W']==pd.Timestamp('2026-11-06T21:00Z')


def test_weekend_keeps_latest_session_and_week():
    result=expected_closes('NVDA','2026-11-14T15:00Z')
    assert all(t==pd.Timestamp('2026-11-13T21:00Z') for t in result.values())


def test_short_session_last_four_hour_bucket_closes_early():
    result=expected_closes('NVDA','2026-11-27T18:01Z')
    assert result['4H']==pd.Timestamp('2026-11-27T18:00Z')
    assert result['1W']==pd.Timestamp('2026-11-27T18:00Z')
    df=candles(pd.DatetimeIndex(['2026-11-27T14:30Z']))
    assert actual_close(df,'4H','NVDA')==result['4H']


def test_stale_candles_never_issue_current_levels():
    snap=SimpleNamespace(ticker='NVDA',provider='test fixture',retrieved_at=pd.Timestamp('2026-11-12T17:00Z'))
    df=candles(pd.bdate_range('2025-01-01',periods=100))
    result=build_timeframe_report(snap,{'1D':df},now='2026-11-12T17:00Z')
    assert result['verdict']=='INCOMPLETE DATA'
    assert all(x['trend']=='UNAVAILABLE' and not x['support'] and not x['resistance'] for x in result['timeframes'].values())


def test_retrieval_time_does_not_change_observation_hash():
    df=candles(pd.bdate_range('2025-01-01',periods=100))
    snap=SimpleNamespace(provider='fixture',fundamentals={},daily=df,hourly=df,quarter=df,minute=df,retrieved_at='first')
    before=data_version(snap);snap.retrieved_at='second'
    assert data_version(snap)==before
    snap.minute=df.copy();snap.minute.iloc[-1,3]=100.1
    assert data_version(snap)!=before
