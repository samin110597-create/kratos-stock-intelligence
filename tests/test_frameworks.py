"""Upstream integration tests; synthetic fixtures stay in tests only."""
import pytest
import numpy as np
import pandas as pd
from kratos.data import MarketDataError
from kratos.frameworks import fingerprint, frame, vectorbt_research, qlib_research


def rows():
    close=100+np.arange(100)*.1+5*np.sin(np.arange(100)/5)
    return [{'time':d.isoformat(),'open':float(p),'high':float(p+1),'low':float(p-1),
        'close':float(p),'volume':1000} for d,p in zip(pd.bdate_range('2025-01-01',periods=100,tz='UTC'),close)]


def test_rejects_duplicate_dates_and_invalid_bars():
    data=rows();data[1]['time']=data[0]['time']
    with pytest.raises(MarketDataError): frame(data)
    data=rows();data[0]['high']=0
    with pytest.raises(MarketDataError): frame(data)


def test_fingerprint_changes_with_input_not_dictionary_order():
    data=rows(); digest=fingerprint(data)
    assert fingerprint([{k:r[k] for k in reversed(r)} for r in data])==digest
    data[0]['close']+=.01
    assert fingerprint(data)!=digest


def test_real_vectorbt_costs_and_results():
    pytest.importorskip('vectorbt')
    result=vectorbt_research(rows())
    assert result['closed_trades']>0
    assert len(result['equity'])==100
    assert result['max_drawdown']<=0
    assert result['assumptions']['fee_per_fill']>0


def test_real_qlib_future_changes_do_not_change_past_predictions():
    pytest.importorskip('qlib')
    data=rows();before=qlib_research(data,'TEST')
    for r in data[-8:]:
        for field in ('open','high','low','close'):r[field]*=1.1
    after=qlib_research(data,'TEST')
    assert before['predictions'][:10]==after['predictions'][:10]
    assert before['test_samples']>=20
    assert all(p['training_last_feature_date']<p['asof'] for p in before['predictions'])
