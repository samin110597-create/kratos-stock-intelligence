"""Re-analyze already published closed candles; no download or ledger mutation."""
import json
from pathlib import Path
import pandas as pd
from kratos.price_plan import build_plan


def refine(path=Path('site/data/snapshots.json')):
    data=json.loads(path.read_text())
    plans={}
    for symbol,item in data['tickers'].items():
        frames={}
        for tf, candles in item.get('technical',{}).get('candles',{}).items():
            if not candles: continue
            df=pd.DataFrame(candles).rename(columns={x:x.title() for x in ('open','high','low','close','volume')})
            df.index=pd.to_datetime(df.pop('time'),utc=True)
            frames[tf]=df
        plan=build_plan(frames)
        plan['archive_reanalysis']=True
        plan['based_on_date']=item.get('last_closed_bar_date')
        plan['history_scope']='Re-analysis of at most 100 already-published completed candles per timeframe; not a frozen forward forecast.'
        plan['source_retrieved_at']=item.get('retrieved_at_utc')
        plans[symbol]=plan
    path.with_name('plans.json').write_text(json.dumps(plans,indent=2,allow_nan=False)+'\n')

if __name__=='__main__': refine()
