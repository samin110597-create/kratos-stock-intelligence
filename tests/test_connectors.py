import json
import httpx
import pytest
from kratos.connectors import Connectors,ConnectorError

def client(tmp_path,monkeypatch,handler):
    monkeypatch.setenv('FINNHUB_API_KEY','SECRET_VALUE')
    return Connectors(tmp_path/'budget.db',httpx.Client(transport=httpx.MockTransport(handler)),clock=lambda:100000)

def test_timestamp_cache_and_no_secret_in_result(tmp_path,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req);return httpx.Response(200,json={'c':100,'t':1700000000})
    c=client(tmp_path,monkeypatch,handler);a=c.fetch('finnhub');b=c.fetch('finnhub')
    assert len(calls)==1 and a==b and a['source_timestamp'].startswith('2023-11')
    assert 'SECRET_VALUE' not in json.dumps(a)

def test_budget_survives_new_client(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch,lambda r:httpx.Response(200,json={'c':1,'t':1}))
    for i in range(30):c.fetch('finnhub',f'S{i}')
    c2=client(tmp_path,monkeypatch,lambda r:pytest.fail('Network after budget'))
    with pytest.raises(ConnectorError,match='budget'):c2.fetch('finnhub','EXTRA')

def test_errors_never_leak_url_or_provider_text(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch,lambda r:httpx.Response(403,text='token=SECRET_VALUE'))
    with pytest.raises(ConnectorError) as e:c.fetch('finnhub')
    assert 'SECRET_VALUE' not in str(e.value)

def test_alpha_soft_rate_limit_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv('ALPHA_VANTAGE_API_KEY','SECRET')
    c=client(tmp_path,monkeypatch,lambda r:httpx.Response(200,json={'Information':'premium'}))
    with pytest.raises(ConnectorError):c.fetch('alpha_vantage')

def test_alpaca_forces_indicative_and_does_not_fabricate_oi(tmp_path,monkeypatch):
    monkeypatch.setenv('ALPACA_API_KEY','key');monkeypatch.setenv('ALPACA_SECRET_KEY','secret')
    def handler(r):
        assert r.url.params['feed']=='indicative'
        return httpx.Response(200,json={'snapshots':{'NVDA':{'latestQuote':{'bp':1}}},'next_page_token':'more'})
    r=client(tmp_path,monkeypatch,handler).fetch('alpaca')
    assert 'open_interest' not in json.dumps(r) and r['payload']['next_page_token']=='more'

def test_fred_vintage_is_explicit(tmp_path,monkeypatch):
    monkeypatch.setenv('FRED_API_KEY','key')
    def handler(r):
        assert r.url.params['realtime_start']=='2020-01-01'
        assert r.url.params['realtime_end']=='2020-01-01'
        return httpx.Response(200,json={'observations':[]})
    client(tmp_path,monkeypatch,handler).fetch('fred','DGS10',vintage='2020-01-01')

def test_occ_forbidden_never_becomes_zero_oi():
    from kratos.occ import fetch_daily_report
    with pytest.raises(ConnectorError,match='403'):
        fetch_daily_report('2026-01-05',httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(403))))

def test_zero_quote_is_not_an_observation(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch,lambda r:httpx.Response(200,json={'c':0,'t':0}))
    with pytest.raises(ConnectorError,match='schema'):c.fetch('finnhub')


def test_daily_account_adapter_preserves_missing_intraday(monkeypatch):
    import pandas as pd
    from kratos.account_provider import AlphaDailyProvider
    history={str(day.date()):{'1. open':'100','2. high':'102','3. low':'99','4. close':'101','5. volume':'1000'} for day in pd.bdate_range('2026-01-01',periods=100)}
    monkeypatch.setattr('kratos.account_provider.Connectors.fetch',lambda *a,**k:{'payload':{'Time Series (Daily)':history},'retrieved_at_utc':'2026-10-21T16:00:00+00:00'})
    r=AlphaDailyProvider().fetch('NVDA')
    assert len(r.daily)==100 and r.minute.empty and r.hourly.empty and r.quote=={}
