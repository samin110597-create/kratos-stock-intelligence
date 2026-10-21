"""Read-only on-demand KRATOS API + dashboard; python server.py."""
from collections import OrderedDict, deque
from datetime import datetime, timezone
import os
import hmac
from pathlib import Path
from threading import BoundedSemaphore, Lock
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from kratos.engine import analyze
from kratos.data import valid_symbol, MarketDataError, ROUTER
from kratos.calendar import calendar_name
from scripts.publish_snapshot import pack, audit_summary

app=FastAPI(title='KRATOS Research API',version='0.3.0',docs_url='/api/docs',redoc_url=None)
origins=[x.strip() for x in os.getenv('KRATOS_ALLOWED_ORIGINS','https://samin110597-create.github.io').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET'],allow_headers=['Content-Type','Authorization'])
lock=Lock();requests=OrderedDict();workers=BoundedSemaphore(2)

def throttle(request):
    # Do not trust attacker-controlled X-Forwarded-For. Configure trusted proxies at deployment.
    key=request.client.host if request.client else 'unknown';now=time.monotonic()
    with lock:
        times=requests.setdefault(key,deque())
        while times and times[0]<now-60: times.popleft()
        if len(times)>=12: raise HTTPException(429,'Too many requests. Try again in one minute.',headers={'Retry-After':'60'})
        times.append(now);requests.move_to_end(key)
        while len(requests)>2048: requests.popitem(last=False)

@app.middleware('http')
async def headers(request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response

def personal_access(request):
    token=os.getenv('KRATOS_ACCESS_TOKEN','')
    if token:
        supplied=request.headers.get('authorization','')
        if not hmac.compare_digest(supplied,'Bearer '+token):
            raise HTTPException(401,'Personal research access token required')
    elif os.getenv('KRATOS_BIND','127.0.0.1') not in ('127.0.0.1','localhost','::1'):
        raise HTTPException(503,'Set a private access token before exposing personal-use data')

@app.get('/api/providers')
def providers(request:Request):
    personal_access(request)
    from kratos.connectors import status
    return status()

@app.get('/api/source/{provider}')
def source(provider:str,request:Request,symbol:str='NVDA',vintage:str|None=None):
    personal_access(request);throttle(request)
    from kratos.connectors import Connectors,ConnectorError
    if provider=='twelve_data': raise HTTPException(403,'Basic data is internal non-display; use the private diagnostic, not a dashboard feed')
    try: return Connectors().fetch(provider,symbol,vintage=vintage)
    except ConnectorError as exc: raise HTTPException(503,str(exc)) from None
    except ValueError: raise HTTPException(422,'Invalid request') from None

@app.get('/api/paths')
def paths(request:Request,symbol:str,horizon:int=5):
    personal_access(request);throttle(request)
    if horizon not in (5,20): raise HTTPException(422,'Use 5 or 20 sessions')
    if not workers.acquire(blocking=False): raise HTTPException(503,'Analyzer busy')
    try:
        from kratos.target_paths import walk_forward_paths
        result=analyze(valid_symbol(symbol))
        return walk_forward_paths(result.technical['daily'],horizon)
    except Exception: raise HTTPException(503,'Path research unavailable; no probability issued') from None
    finally: workers.release()

@app.get('/api/health')
def health():
    return {'status':'ok','version':'0.3.0','time_utc':datetime.now(timezone.utc).isoformat(),
            'providers':ROUTER.health,'live_data_guarantee':False,
            'forecast_recording':'disabled on public API; scheduled publisher records observations',
            'storage':'local SQLite; persistence depends on host; public ledger versioned in Git',
            'institutional_feeds':'unavailable'}

@app.get('/api/analyze')
def analysis(request:Request,symbol:str):
    throttle(request)
    personal_access(request)
    try: ticker=valid_symbol(symbol);calendar_name(ticker)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    if not workers.acquire(blocking=False): raise HTTPException(503,'Analyzer busy. Try again shortly.',headers={'Retry-After':'15'})
    try:
        result=analyze(ticker)
        return {'generated_at_utc':datetime.now(timezone.utc).isoformat(),'ticker':pack(ticker,result)}
    except (MarketDataError,ValueError) as exc:
        raise HTTPException(503,str(exc)[:240]) from exc
    except Exception as exc:
        # Do not disclose credential-bearing provider URLs or stack traces.
        raise HTTPException(503,'Analysis failed; no market signal generated.') from exc
    finally: workers.release()

@app.get('/config.json')
def config():
    return {'api_url':'','same_origin_api':True,'refresh_minutes':15,'personal_access_required':bool(os.getenv('KRATOS_ACCESS_TOKEN'))}

app.mount('/',StaticFiles(directory=Path(__file__).parent/'site',html=True),name='dashboard')
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host=os.getenv('KRATOS_BIND','127.0.0.1'),port=int(os.getenv('PORT','7860')),proxy_headers=False)
