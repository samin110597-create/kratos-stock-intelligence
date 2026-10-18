from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from kratos.audit import connect, record, resolve, recent_records, audit_stats


def sample():
    et=datetime.now(ZoneInfo('America/Toronto'))
    anchor=(et-timedelta(days=1)).date().isoformat()
    tech={'close':100.,'asof_bar_date':anchor}
    dec={'bias':'UP','classification':'WAIT','entry_zone':(99.,101.),
         'stop':97.,'targets':[103.,106.,112.],
         'ranges':{'5':{'lower':96.,'upper':104.},'20':{'lower':92.,'upper':108.}}}
    return tech,dec


def test_immutable_forecast_no_duplicate(tmp_path):
    path=str(tmp_path/'db.sqlite3')
    t,d=sample()
    ids=record('NVDA',t,d,'TEST_PROVIDER',path)
    assert len(ids)==2
    assert record('NVDA',t,d,'TEST_PROVIDER',path)==[]
    with connect(path) as conn:
        rows=conn.execute('select count(*) from forecasts').fetchone()[0]
        assert rows==2


def test_reject_old_retroactive_prediction(tmp_path):
    path=str(tmp_path/'db.sqlite3')
    t,d=sample()
    t['asof_bar_date']='2020-01-01'
    with pytest.raises(ValueError,match='old'):
        record('NVDA',t,d,'TEST_PROVIDER',path)


def test_no_outcome_before_record_time(tmp_path):
    path=str(tmp_path/'db.sqlite3')
    t,d=sample()
    record('NVDA',t,d,'TEST_PROVIDER',path)
    # Historical future dates from years ago must NEVER resolve a newly saved record.
    past=pd.date_range('2020-01-01',periods=200,freq='B')
    df=pd.DataFrame({'Close':[100+i*.1 for i in range(200)]},index=past)
    assert resolve('NVDA',df,path)==0
    assert audit_stats(path)[5]['resolved']==0


def test_matured_forecast_can_resolve_without_changing_original(tmp_path):
    path=str(tmp_path/'db.sqlite3')
    t,d=sample()
    record('NVDA',t,d,'TEST_PROVIDER',path)
    # Backdate the recorded_at date in the test database ONLY to simulate time passing.
    with connect(path) as conn:
        conn.execute("UPDATE forecasts SET source_bar_date='2026-01-02', recorded_at_utc='2026-01-02T22:00:00+00:00'")
    past=pd.date_range('2025-12-29',periods=40,freq='B')
    df=pd.DataFrame({'Close':[100+i*.15 for i in range(40)]},index=past)
    assert resolve('NVDA',df,path)==2
    stats=audit_stats(path)
    assert stats[5]['resolved']==1
    assert stats[20]['resolved']==1
    with connect(path) as conn:
        row=conn.execute('SELECT base_close, target_1, status FROM forecasts LIMIT 1').fetchone()
    assert row==(100.,103.,'RESOLVED')
