from datetime import datetime, timezone
import copy
import sqlite3
import pandas as pd
import pytest
from kratos.audit import connect,record,resolve,records,audit_stats,export_events,verify_events,import_events
from kratos.calendar import schedule
NOW=datetime(2026,1,2,22,tzinfo=timezone.utc)
def sample():
    return {'close':100.,'asof_bar_date':'2026-01-02'}, {'bias':'UP','classification':'WAIT','entry_zone':(99.,101.),'stop':97.,'targets':[103.,106.,112.],'ranges':{'5':{'lower':96.,'upper':104.},'20':{'lower':92.,'upper':108.}}}
def test_immutable_forecast_no_duplicate(tmp_path):
    p=str(tmp_path/'db');t,d=sample()
    assert len(record('NVDA',t,d,'fixture',p,now=NOW))==2
    assert record('NVDA',t,d,'fixture',p,now=NOW)==[]
    with connect(p) as db:
        with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE events SET payload='{}'")
        with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM events')
def test_reject_old_retroactive_prediction(tmp_path):
    t,d=sample();t['asof_bar_date']='2020-01-01'
    with pytest.raises(ValueError,match='old'): record('NVDA',t,d,'fixture',str(tmp_path/'db'),now=NOW)
def test_exact_maturity_and_separate_outcomes(tmp_path):
    p=str(tmp_path/'db');t,d=sample();record('NVDA',t,d,'fixture',p,now=NOW)
    original=copy.deepcopy(export_events(p))
    dates=schedule('NVDA','2026-01-02','2026-02-28').index
    frame=pd.DataFrame({'Close':[100+i*.2 for i in range(len(dates))]},index=dates)
    assert resolve('NVDA',frame,p,now=NOW)==0
    assert resolve('NVDA',frame.drop(pd.Timestamp('2026-01-09')),p,now=datetime(2026,3,1,tzinfo=timezone.utc))==1
    assert audit_stats(p)[5]['resolved']==0
    assert resolve('NVDA',frame,p,now=datetime(2026,3,1,tzinfo=timezone.utc))==1
    assert export_events(p)[:2]==original
    assert len(export_events(p))==4
    assert verify_events(export_events(p))
def test_tampering_detected_and_export_roundtrip(tmp_path):
    p=str(tmp_path/'db');q=str(tmp_path/'restored');t,d=sample();record('NVDA',t,d,'fixture',p,now=NOW)
    events=export_events(p); import_events(events,q);assert export_events(q)==events
    events[0]['payload']['base_close']=999
    with pytest.raises(ValueError):verify_events(events)
def test_revised_price_history_is_unscorable(tmp_path):
    p=str(tmp_path/'db');t,d=sample();record('NVDA',t,d,'fixture',p,now=NOW)
    frame=pd.DataFrame({'Close':50.},index=schedule('NVDA','2026-01-02','2026-02-28').index)
    resolve('NVDA',frame,p,now=datetime(2026,3,1,tzinfo=timezone.utc))
    assert all(x['outcome']['status']=='UNSCORABLE_REVISION' for x in records(p))
    assert audit_stats(p)[5]['direction_evaluated']==0

def test_publisher_serializes_read_compute_append(tmp_path,monkeypatch):
    from filelock import FileLock, Timeout
    import scripts.publish_snapshot as publisher
    monkeypatch.setattr(publisher,'DATA',tmp_path)
    with FileLock(str(tmp_path/'publisher.lock')):
        with pytest.raises(Timeout): publisher.run(['NVDA'],analyzer=lambda _:None)

def test_publisher_refuses_concurrent_history_replacement(tmp_path,monkeypatch):
    import scripts.publish_snapshot as publisher
    monkeypatch.setattr(publisher,'DATA',tmp_path)
    monkeypatch.setattr(publisher,'SNAPSHOTS',tmp_path/'snapshots.json')
    monkeypatch.setattr(publisher,'LEDGER',tmp_path/'legacy.json')
    def changing_provider(_):
        (tmp_path/'events.jsonl').write_text('concurrent writer\n')
        raise ValueError('fixture')
    with pytest.raises(RuntimeError,match='concurrently'): publisher.run(['NVDA'],analyzer=changing_provider)
    assert (tmp_path/'events.jsonl').read_text()=='concurrent writer\n'


def test_new_plan_version_preserves_previous_forecasts(tmp_path):
    p=str(tmp_path/'db');t,d=sample()
    record('NVDA',t,d,'fixture',p,now=NOW)
    original=copy.deepcopy(export_events(p))
    d['model_version']='structure-plan-v1'
    assert len(record('NVDA',t,d,'fixture',p,now=NOW))==2
    assert export_events(p)[:2]==original
    assert all(x['model_version']=='structure-plan-v1' for x in records(p)[-2:])
