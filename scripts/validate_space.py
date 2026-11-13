"""External acceptance check; no credentials needed or printed."""
import json,time,urllib.request,urllib.error
BASE='https://smit1105-kratos-backend.hf.space'
def get(path,timeout=150):
    try:
        with urllib.request.urlopen(BASE+path,timeout=timeout) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        try:return e.code,json.load(e)
        except Exception:return e.code,{'detail':'Non-JSON error response'}
for attempt in range(18):
    try:
        code,body=get('/api/health',30)
        if code==200 and body.get('status')=='ok':break
    except Exception:pass
    print('Waiting for Space startup',attempt+1,flush=True);time.sleep(10)
else:raise RuntimeError('Backend did not become healthy')
print('HEALTH',json.dumps(body),flush=True)
results=[]
for symbol in ('NVDA','GOOG','RY.TO','AAPL'):
    try:
        status,data=get('/api/analyze?symbol='+symbol+'&require_fresh=true')
        ticker=data.get('ticker',{})
        record={'symbol':symbol,'http_status':status,'detail':data.get('detail'),
            'source':ticker.get('source'),'timeframe_report':ticker.get('timeframe_report'),
            'freshness':ticker.get('freshness'),'data_version':ticker.get('data_version')}
    except Exception as exc:record={'symbol':symbol,'error':type(exc).__name__}
    results.append(record);print('PROBE',json.dumps(record),flush=True)
if not all(r.get('http_status')==200 for r in results):raise RuntimeError('At least one ticker failed strict freshness acceptance; inspect PROBE records')
