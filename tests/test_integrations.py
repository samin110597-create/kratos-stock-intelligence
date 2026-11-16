from unittest.mock import patch
from fastapi.testclient import TestClient
import server
from kratos.integrations import run_engine, _cache


def test_engine_rejects_unsupported_framework_and_ticker():
    with server.lock: server.requests.clear()
    client=TestClient(server.app)
    with patch('server.analyze') as analyze:
        assert client.get('/api/engine/fake?symbol=NVDA').status_code==422
        assert client.get('/api/engine/openbb?symbol=../bad').status_code==422
        analyze.assert_not_called()


def test_engine_failure_never_exposes_secrets_or_substitutes_results():
    _cache.clear()
    payload={'provider':'test','technical':{'candles':{'1D':[]}},'last_closed_bar_date':'2026-11-13','retrieved_at_utc':'2026-11-16T15:00:00Z'}
    with patch('kratos.integrations.openbb_statements',side_effect=RuntimeError('SECRET_TOKEN')):
        result=run_engine('NVDA','openbb',payload)
    assert result['engines']['openbb']['status']=='unavailable'
    assert 'SECRET' not in str(result)
    assert not _cache


def test_engine_cache_preserves_original_retrieval_time():
    _cache.clear()
    payload={'provider':'test','technical':{'candles':{'1D':[]}},'last_closed_bar_date':'2026-11-13','retrieved_at_utc':'2026-11-16T15:00:00Z'}
    with patch('kratos.integrations.openbb_statements',return_value={'status':'operational'}) as run:
        before=run_engine('NVDA','openbb',payload)
        payload['retrieved_at_utc']='2026-11-16T15:03:00Z'
        after=run_engine('NVDA','openbb',payload)
    assert run.call_count==1
    assert after['calculated_at_utc']==before['calculated_at_utc']
    assert after['source_retrieved_at_utc']=='2026-11-16T15:00:00Z'
    _cache.clear()
