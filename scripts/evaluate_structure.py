"""Fixed last-504-bar holdout; disjoint five-session windows, frozen prior levels.
No fitting or parameter search. Revised daily history; not independent live evidence.
"""
import json
import sys
import pandas as pd
from kratos.price_plan import build_plan, VERSION


def evaluate(df):
    outcomes=[];signals=0;cancelled=0
    for i in range(max(252,len(df)-504),len(df)-5,5):
        prefix=df.iloc[:i+1]
        # Exclude the current calendar week: it may not be completed.
        weeks=prefix.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
        weeks=weeks.loc[weeks.index<prefix.index[-1].normalize()-pd.Timedelta(days=4)]
        p=build_plan({'1D':prefix.tail(252),'1W':weeks})
        if not p['candidate']: continue
        signals+=1;future=df.iloc[i+1:i+6];entry=float(future.Open.iloc[0]);lo,hi=p['entry_zone']
        if not lo<=entry<=hi: cancelled+=1;continue
        stop=p['stop'];target=p['targets'][0];exit_price=float(future.Close.iloc[-1]);status='TIMEOUT';ambiguous=False
        for _,bar in future.iterrows():
            if bar.Open<=stop: exit_price=float(bar.Open);status='STOP GAP';break
            if bar.Open>=target: exit_price=target;status='TARGET';break
            if bar.Low<=stop:
                exit_price=stop;status='STOP';ambiguous=bool(bar.High>=target);break
            if bar.High>=target: exit_price=target;status='TARGET';break
        outcomes.append({'origin':str(df.index[i].date()),'status':status,'ambiguous':ambiguous,'net_return':exit_price/entry-1-.002})
    return {'model':VERSION,'evaluation':'Last 504 bars; every fifth origin; next-open fill only inside fixed entry zone; five-session holding cap; 20bp round-trip costs; ambiguous bars stop-first',
            'rule_candidates':signals,'cancelled_entries':cancelled,'trades':len(outcomes),'net_wins':sum(x['net_return']>0 for x in outcomes),
            'mean_net_return':sum(x['net_return'] for x in outcomes)/len(outcomes) if outcomes else None,
            'outcomes':outcomes,'promoted':False,'limitations':'Single revised-price series; no independent live validation; daily/weekly only. Not comparable to the separate logistic target experiment.'}

if __name__=='__main__':
    frame=pd.read_csv(sys.argv[1],index_col=0)
    frame.index=pd.to_datetime(frame.index,utc=True).tz_convert('America/Toronto').tz_localize(None)
    print(json.dumps(evaluate(frame),indent=2))
