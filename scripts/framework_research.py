"""Scheduled offline research; content-addressed records preserve prior runs in Git."""
import json
from pathlib import Path
from kratos.frameworks import research_record, fingerprint


def run():
    root=Path(__file__).resolve().parents[1]
    data=root/'site/data'
    snapshots=json.loads((data/'snapshots.json').read_text())['tickers']
    records={}
    existing=json.loads((data/'frameworks.json').read_text()).get('tickers',{}) if (data/'frameworks.json').exists() else {}
    implementation=fingerprint((root/'kratos/frameworks.py').read_text())
    for symbol,snapshot in snapshots.items():
        if snapshot.get('error'): continue
        prior=existing.get(symbol,{})
        rows=snapshot.get('technical',{}).get('candles',{}).get('1D',[])
        if (prior.get('implementation_sha256')==implementation and prior.get('input_sha256')==fingerprint(rows)
            and prior.get('source_retrieved_at_utc')==snapshot.get('retrieved_at_utc')
            and all(prior.get('engines',{}).get(k,{}).get('status')=='operational_historical' for k in ('qlib','vectorbt'))):
            records[symbol]=prior
            print(symbol,'unchanged inputs; retained prior calculation timestamp',flush=True)
            continue
        record=research_record(symbol,snapshot)
        record['implementation_sha256']=implementation
        records[symbol]=record
        archive=data/'framework-runs'/symbol
        archive.mkdir(parents=True,exist_ok=True)
        path=archive/(fingerprint(record)+'.json')
        with path.open('x') as f: json.dump(record,f,indent=2,allow_nan=False)
        print(symbol,{k:v['status'] for k,v in record['engines'].items()},flush=True)
    (data/'frameworks.json').write_text(json.dumps({'tickers':records},indent=2,allow_nan=False)+'\n')

if __name__=='__main__': run()
