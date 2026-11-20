"""Validate actual LEAN output before publishing a successful integration."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validated_result(folder):
    for path in sorted(Path(folder).glob('*.json')):
        obj=json.loads(path.read_text())
        if not isinstance(obj,dict):continue  # order-events is a separate JSON array
        obj={key[:1].upper()+key[1:]:value for key,value in obj.items()}
        state=obj.get('State',{})
        if state.get('RuntimeError') or obj.get('RuntimeError'):
            raise RuntimeError('LEAN runtime error; result must not be published')
        stats=obj.get('Statistics',{})
        runtime=obj.get('RuntimeStatistics',{})
        if (state.get('Status')=='Completed' and stats
                and int(runtime.get('Input observations','0'))>100
                and int(stats.get('Total Orders','0'))>0):
            return obj
    raise RuntimeError('No completed LEAN simulation with observations and executed orders')


def run(root=Path('lean-work'),output=Path('site/data')):
    source=json.loads((root/'input.json').read_text())
    result=validated_result(root/'results')
    record={**{key:value for key,value in source.items() if key!='rows'},
        'calculated_at_utc':result['State']['EndTime'],
        'collected_at_utc':datetime.now(timezone.utc).isoformat(),
        'input_sha256':fingerprint(source['rows']),
        'engines':{'lean':{
            'status':'operational_historical','version':(root/'image.txt').read_text().strip(),
            'method':'LEAN custom-data 10/30 moving-average strategy; signal at close, next reported open execution; 95% allocation',
            'statistics':result['Statistics'],'runtime_statistics':result['RuntimeStatistics'],
            'limitations':['Custom reported open/close observations, not a licensed exchange execution feed.',
                '0.10% fee and 0.05% slippage per fill; no order-book simulation, dividends or fill-capacity model.',
                'Benchmark-dependent statistics use a constant benchmark, not a market index.',
                'Single-symbol simulation in nominal price units. No FX conversion or live brokerage orders.']}}}
    archive=output/'lean-runs';archive.mkdir(parents=True,exist_ok=True)
    (archive/(fingerprint(record)+'.json')).write_text(json.dumps(record,indent=2)+'\n')
    (output/'lean-latest.json').write_text(json.dumps({'tickers':{source['symbol']:record}},indent=2)+'\n')
    print('Verified LEAN:',source['symbol'],result['Statistics']['Total Orders'],'orders;',result['RuntimeStatistics']['Input observations'],'observations')

if __name__=='__main__':run()
