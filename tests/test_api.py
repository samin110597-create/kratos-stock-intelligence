from fastapi.testclient import TestClient
from unittest.mock import patch
from kratos.data import MarketDataError
import server

def test_health_does_not_claim_live_or_durable():
    client=TestClient(server.app)
    r=client.get('/api/health')
    assert r.status_code==200 and not r.json()['live_data_guarantee']
    assert r.headers['cache-control']=='no-store'

def test_invalid_symbol_never_reaches_provider():
    with patch('server.analyze') as analyze:
        assert TestClient(server.app).get('/api/analyze',params={'symbol':'../etc/passwd'}).status_code==422
        analyze.assert_not_called()

def test_provider_failure_is_explicit_not_fixture_price():
    with patch('server.analyze',side_effect=MarketDataError('Provider unavailable')):
        r=TestClient(server.app).get('/api/analyze',params={'symbol':'NVDA'})
        assert r.status_code==503 and 'ticker' not in r.json()

def test_unknown_exception_redacts_secret():
    with patch('server.analyze',side_effect=RuntimeError('token=SECRET')):
        r=TestClient(server.app).get('/api/analyze',params={'symbol':'NVDA'})
        assert 'SECRET' not in r.text

def test_site_and_backend_config():
    client=TestClient(server.app)
    assert client.get('/').status_code==200
    assert client.get('/config.json').json()['same_origin_api']

def test_no_public_forecast_write_endpoint():
    assert TestClient(server.app).post('/api/forecasts',json={}).status_code in (404,405)

def test_success_payload_is_real_analyzer_result():
    with patch('server.analyze',return_value=object()), patch('server.pack',return_value={'ticker':'RY.TO','provider':'fixture'}):
        r=TestClient(server.app).get('/api/analyze',params={'symbol':'TSX:RY'})
        assert r.status_code==200 and r.json()['ticker']['ticker']=='RY.TO'

def test_rate_limit_is_enforced():
    with server.lock: server.requests.clear()
    with patch('server.analyze',side_effect=MarketDataError('unavailable')):
        client=TestClient(server.app)
        for _ in range(12):client.get('/api/analyze?symbol=NVDA')
        assert client.get('/api/analyze?symbol=NVDA').status_code==429
    with server.lock: server.requests.clear()


def test_hosted_personal_feed_requires_auth(monkeypatch):
    monkeypatch.setenv('KRATOS_BIND','0.0.0.0')
    monkeypatch.delenv('KRATOS_ACCESS_TOKEN',raising=False)
    assert TestClient(server.app).get('/api/providers').status_code==503
    monkeypatch.setenv('KRATOS_ACCESS_TOKEN','private-test')
    c=TestClient(server.app)
    assert c.get('/api/providers').status_code==401
    assert c.get('/api/providers',headers={'Authorization':'Bearer private-test'}).status_code==200


def test_explicit_public_analysis_does_not_unlock_private_endpoints(monkeypatch):
    monkeypatch.setenv('KRATOS_BIND','0.0.0.0')
    monkeypatch.setenv('KRATOS_ACCESS_TOKEN','private-test')
    monkeypatch.setenv('KRATOS_PUBLIC_ANALYSIS','true')
    with server.lock: server.requests.clear()
    c=TestClient(server.app)
    with patch('server.analyze',return_value=object()), patch('server.pack',return_value={'ticker':'AAPL'}):
        assert c.get('/api/analyze?symbol=AAPL').status_code==200
    assert not c.get('/config.json').json()['personal_access_required']
    for path in ['/api/providers','/api/source/fmp?symbol=AAPL','/api/paths?symbol=AAPL']:
        assert c.get(path).status_code==401
    monkeypatch.setenv('KRATOS_PUBLIC_ANALYSIS','false')
    assert c.get('/api/analyze?symbol=AAPL').status_code==401
    assert c.get('/config.json').json()['personal_access_required']
    with server.lock: server.requests.clear()


def test_strict_endpoint_rejects_stale_candles_without_prices():
    from types import SimpleNamespace
    with server.lock: server.requests.clear()
    snapshot=SimpleNamespace(freshness=lambda **kwargs:{'live_enough':True})
    result=SimpleNamespace(snapshot=snapshot)
    payload={'ticker':'NVDA','price':123,'timeframe_report':{'timeframes':{tf:{'freshness':'STALE_OR_MISSING'} for tf in ('1H','4H','1D','1W')}}}
    with patch('server.analyze',return_value=result),patch('server.pack',return_value=payload):
        r=TestClient(server.app).get('/api/analyze?symbol=NVDA&require_fresh=true')
        assert r.status_code==409
        assert 'price' not in r.json() and 'ticker' not in r.json()


def test_strict_endpoint_rejects_old_market_hours_quote():
    from types import SimpleNamespace
    with server.lock: server.requests.clear()
    result=SimpleNamespace(snapshot=SimpleNamespace(freshness=lambda **kwargs:{'live_enough':False}))
    payload={'ticker':'NVDA','timeframe_report':{'timeframes':{tf:{'freshness':'LATEST_COMPLETED'} for tf in ('1H','4H','1D','1W')}}}
    with patch('server.analyze',return_value=result),patch('server.pack',return_value=payload),patch('kratos.calendar.session_state',return_value={'market_open':True}):
        assert TestClient(server.app).get('/api/analyze?symbol=NVDA&require_fresh=true').status_code==409


def test_strict_endpoint_accepts_latest_closed_market_history():
    from types import SimpleNamespace
    with server.lock: server.requests.clear()
    result=SimpleNamespace(snapshot=SimpleNamespace(freshness=lambda **kwargs:{'live_enough':False}))
    payload={'ticker':'NVDA','timeframe_report':{'timeframes':{tf:{'freshness':'LATEST_COMPLETED'} for tf in ('1H','4H','1D','1W')}}}
    with patch('server.analyze',return_value=result),patch('server.pack',return_value=payload),patch('kratos.calendar.session_state',return_value={'market_open':False}):
        assert TestClient(server.app).get('/api/analyze?symbol=NVDA&require_fresh=true').status_code==200
