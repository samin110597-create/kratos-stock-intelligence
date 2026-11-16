import json
from pathlib import Path
from datetime import datetime,timezone
from kratos.frameworks import fingerprint
root=Path('lean-work');source=json.loads((root/'input.json').read_text());result=None
for path in (root/'results').glob('*.json'):
    obj=json.loads(path.read_text())
    if obj.get('Statistics') and obj.get('RuntimeStatistics',{}).get('Input observations'):
        if obj.get('RuntimeError'):raise RuntimeError('LEAN runtime error')
        result=obj;break
if result is None:raise RuntimeError('No successful LEAN statistics with input observations')
record={**{k:v for k,v in source.items() if k!='rows'},'calculated_at_utc':datetime.now(timezone.utc).isoformat(),
 'input_sha256':fingerprint(source['rows']),'engines':{'lean':{
 'status':'operational_historical','version':(root/'image.txt').read_text().strip(),
 'method':'LEAN custom-data 10/30 moving-average strategy; signal at close, next reported open execution; 95% allocation',
 'statistics':result['Statistics'],'runtime_statistics':result['RuntimeStatistics'],
 'limitations':['Custom reported open/close observations, not a licensed exchange execution feed.',
 '0.10% fee and 0.05% slippage per fill; no order-book simulation, dividends or fill-capacity model.',
 'Only NVDA has been run. No live brokerage connection or orders.']}}}
p=Path('site/data/lean-runs');p.mkdir(parents=True,exist_ok=True)
(p/(fingerprint(record)+'.json')).write_text(json.dumps(record,indent=2)+'\n')
Path('site/data/lean-latest.json').write_text(json.dumps({'tickers':{'NVDA':record}},indent=2)+'\n')
