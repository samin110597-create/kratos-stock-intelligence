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
