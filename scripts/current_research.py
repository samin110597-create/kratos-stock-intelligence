"""Hosted scheduled training and immutable pre-outcome model forecasts.

Never used by an HTTP request. A failed symbol retains no claim of a new forecast.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
from kratos.engine import analyze
from kratos.data import valid_symbol
from kratos.forecast_outcomes import resolve
from kratos.frameworks import research_record, fingerprint
from scripts.publish_snapshot import pack

ROOT=Path(__file__).resolve().parents[1]/'site/data'

def run():
    index={}
    for raw in os.getenv('RESEARCH_SYMBOLS','NVDA,GOOG,RY.TO,AAPL').split(','):
        symbol=valid_symbol(raw)
        try:
            payload=pack(symbol,analyze(symbol))
            outcomes=ROOT/'forecast-outcomes'
            outcomes.mkdir(parents=True,exist_ok=True)
            for previous in (ROOT/'framework-runs'/symbol).glob('*.json'):
                destination=outcomes/(previous.stem+'.json')
                if destination.exists():continue
                resolved=resolve(json.loads(previous.read_text()),payload['technical']['candles']['1D'])
                if resolved:
                    resolved['forecast_record_id']=previous.stem
                    resolved['outcome_source']=payload['provider']
                    resolved['outcome_source_retrieved_at_utc']=payload['retrieved_at_utc']
                    destination.write_text(json.dumps(resolved,allow_nan=False,indent=2)+'\n')
            record=research_record(symbol,payload)
            archive=ROOT/'framework-runs'/symbol
            archive.mkdir(parents=True,exist_ok=True)
            path=archive/(fingerprint(record)+'.json')
            path.write_text(json.dumps(record,allow_nan=False,indent=2)+'\n')
            index[symbol]=record
            print(symbol,{k:v['status'] for k,v in record['engines'].items()},flush=True)
        except Exception as exc:
            index[symbol]={'symbol':symbol,'engines':{},'error':type(exc).__name__,
                'calculated_at_utc':datetime.now(timezone.utc).isoformat()}
            print(symbol,'FAILED',type(exc).__name__,flush=True)
    (ROOT/'current-research.json').write_text(json.dumps({'tickers':index},allow_nan=False,indent=2)+'\n')

if __name__=='__main__':run()
