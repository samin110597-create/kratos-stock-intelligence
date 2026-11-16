"""Actual upstream adapters. A failed engine never fabricates an alternative result."""
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from threading import Lock
from collections import OrderedDict
import json
import time
from .frameworks import fingerprint, vectorbt_research

_lock = Lock()
_cache = OrderedDict()


def openbb_statements(symbol):
    # OpenBB Core discovers the installed equity and yfinance extensions.
    import asyncio
    from openbb_yfinance.models.income_statement import YFinanceIncomeStatementFetcher
    from openbb_yfinance.models.balance_sheet import YFinanceBalanceSheetFetcher
    from openbb_yfinance.models.cash_flow import YFinanceCashFlowStatementFetcher
    fetchers={'income':YFinanceIncomeStatementFetcher,'balance':YFinanceBalanceSheetFetcher,'cash':YFinanceCashFlowStatementFetcher}
    tables = {}
    errors = {}
    for name in ('income', 'balance', 'cash'):
        try:
            response = asyncio.run(fetchers[name].fetch_data(params={'symbol':symbol,'period':'annual','limit':4}, credentials={}))
            tables[name] = [r.model_dump(mode='json') for r in response]
        except Exception as exc:
            errors[name] = type(exc).__name__
    if not any(tables.values()):
        raise ValueError('OpenBB provider returned no statements')
    return {'status':'operational', 'version':version('openbb-core'),
            'method':'OpenBB provider Fetcher pipeline: income statement, balance sheet and cash flow',
            'source':'OpenBB / Yahoo Finance', 'statements':tables, 'missing':errors,
            'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
            'limitations':['Annual reporting periods are not live market observations.',
                          'Provider statements are not independently reconciled to filings.',
                          'Missing statements remain unavailable; no intrinsic value is invented.']}


def run_engine(symbol, engine, payload):
    if engine not in ('openbb','vectorbt'):
        raise ValueError('Unsupported on-demand engine')
    rows=payload['technical']['candles']['1D']
    key=(symbol, engine, fingerprint(rows) if engine=='vectorbt' else datetime.now(timezone.utc).strftime('%Y-%m-%d-%H'))
    # Single worker prevents JIT/provider stampedes; bounded cache is not an audit store.
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        try:
            result=openbb_statements(symbol) if engine=='openbb' else vectorbt_research(rows)
        except Exception as exc:
            result={'status':'unavailable', 'reason':type(exc).__name__+'; upstream calculation failed. No substitute output.'}
        record={'symbol':symbol,'source':payload['provider'],
                'source_retrieved_at_utc':payload['retrieved_at_utc'],
                'data_last_session':payload['last_closed_bar_date'],
                'input_sha256':fingerprint(rows), 'calculated_at_utc':datetime.now(timezone.utc).isoformat(),
                'engines':{engine:result}}
        if engine=='vectorbt': record['input_bars']=rows
        elif result.get('statements'):
            record['input_sha256']=fingerprint(result['statements'])
            record['source']=result['source']
            record['source_retrieved_at_utc']=result['retrieved_at_utc']
            dates=[str(r.get('period_ending') or r.get('date')) for table in result['statements'].values() for r in table if r.get('period_ending') or r.get('date')]
            record['data_last_session']=max(dates) if dates else None
        if result['status']!='unavailable':
            _cache[key]=record
            while len(_cache)>24: _cache.popitem(last=False)
        return record
