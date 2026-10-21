"""Frozen long-only target-before-stop research, not a production trade policy.

Signal uses close i; modeled entry is next open, cancellation on opening outside
barriers. Bar ambiguity is counted separately and conservatively stopped for P&L.
Training, calibration and test windows are chronological and label-embargoed.
No claim that revised historical prices are point-in-time observations.
"""
import hashlib
import numpy as np
import pandas as pd
from .research import features

VERSION='target-before-stop-v1'

def label_path(frame,i,horizon=5,cost_bps=20):
    if horizon<1 or cost_bps<0 or i<20 or i+horizon>=len(frame): return None
    past=frame.iloc[:i+1]
    tr=pd.concat([past.High-past.Low,(past.High-past.Close.shift()).abs(),(past.Low-past.Close.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.tail(14).mean()); ref=float(past.Close.iloc[-1]);risk=1.5*atr
    if not np.isfinite(risk) or risk<=0: return None
    stop=ref-risk;target=ref+2*risk;entry=float(frame.Open.iloc[i+1]);cost=cost_bps/10000
    if stop<=0 or not stop<entry<target: return None
    outcome='TIMEOUT';exit_price=float(frame.Close.iloc[i+horizon]);end=i+horizon;ambiguous=False
    for j in range(i+1,i+horizon+1):
        b=frame.iloc[j]
        if b.Open<=stop: outcome='STOP';exit_price=float(b.Open);end=j;break
        if b.Open>=target: outcome='TARGET';exit_price=target;end=j;break
        if b.Low<=stop and b.High>=target:
            outcome='AMBIGUOUS';ambiguous=True;exit_price=stop;end=j;break
        if b.Low<=stop: outcome='STOP';exit_price=stop;end=j;break
        if b.High>=target: outcome='TARGET';exit_price=target;end=j;break
    return {'origin_index':i,'label_end_index':i+horizon,'exit_index':end,
            'origin':str(frame.index[i]),'entry':entry,'target':target,'stop':stop,'horizon_bars':horizon,
            'outcome':outcome,'ambiguous':ambiguous,'target_before_stop':None if ambiguous else int(outcome=='TARGET'),
            'net_return':exit_price/entry-1-cost,'net_r':(exit_price-entry-entry*cost)/risk}

def logistic(X,y,test):
    mean=X.mean(0);scale=X.std(0);scale[scale<1e-12]=1
    z=np.c_[np.ones(len(X)),(X-mean)/scale];w=np.zeros(z.shape[1])
    for _ in range(150):
        p=1/(1+np.exp(-np.clip(z@w,-30,30)))
        w-=.1*((z.T@(p-y))/len(y)+.01*np.r_[0,w[1:]])
    zz=np.c_[np.ones(len(test)),(test-mean)/scale]
    return 1/(1+np.exp(-np.clip(zz@w,-30,30)))

def calibration_map(raw,y,test):
    # Fixed five bins, shrink sparse bins toward chronological calibration mean.
    bins=np.minimum((raw*5).astype(int),4);out=[]
    for p in test:
        mask=bins==min(int(p*5),4)
        out.append(float((y[mask].sum()+10*y.mean())/(mask.sum()+10)))
    return np.array(out)

def metrics(records,model):
    scored=[r for r in records if r['target_before_stop'] is not None]
    y=np.array([r['target_before_stop'] for r in scored]);p=np.array([r['probabilities'][model] for r in scored])
    selected=[r for r in records if r['probabilities'][model]>=.6]
    returns=np.array([r['net_return'] for r in selected]);curve=np.cumprod(1+returns)
    bins=[]
    for low in (0,.2,.4,.6,.8):
        keep=(p>=low)&(p<(low+.2) if low<.8 else p<=1)
        bins.append({'lower':low,'samples':int(keep.sum()),'mean_probability':float(p[keep].mean()) if keep.any() else None,'target_frequency':float(y[keep].mean()) if keep.any() else None})
    return {'samples':len(scored),'ambiguous_excluded_from_calibration':len(records)-len(scored),
            'brier':float(np.mean((p-y)**2)) if len(y) else None,'calibration_bins':bins,
            'trades_at_fixed_0_6_threshold':len(selected),'net_expectancy_return':float(returns.mean()) if len(returns) else None,
            'wins':sum(r['net_return']>0 for r in selected),'losses':sum(r['net_return']<=0 for r in selected),
            'targets':sum(r['outcome']=='TARGET' for r in selected),'stops':sum(r['outcome'] in ('STOP','AMBIGUOUS') for r in selected),
            'timeouts':sum(r['outcome']=='TIMEOUT' for r in selected),
            'max_drawdown':float(np.min(np.r_[1,curve]/np.maximum.accumulate(np.r_[1,curve])-1)) if len(curve) else None}

def walk_forward_paths(frame,horizon=5,cost_bps=20,min_train=100,calibration_size=30,test_size=12):
    if horizon not in (5,20): raise ValueError('Supported horizons: 5 and 20 bars')
    prices=frame[['Open','High','Low','Close']]
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates: raise ValueError('Ordered unique timestamps required')
    if not np.isfinite(prices.to_numpy()).all() or (prices<=0).any().any(): raise ValueError('Invalid OHLC')
    if ((frame.High<prices.max(axis=1))|(frame.Low>prices.min(axis=1))).any(): raise ValueError('Impossible OHLC')
    x=features(frame.Close).to_numpy();events=[]
    for i in range(40,len(frame)-horizon,horizon):
        row=label_path(frame,i,horizon,cost_bps)
        if row and np.isfinite(x[i]).all(): events.append(row)
    output=[]
    for start in range(min_train+calibration_size+4,len(events),test_size):
        test=events[start:start+test_size];cutoff=test[0]['origin_index']-horizon
        historical=[r for r in events[:start] if r['label_end_index']<cutoff and r['target_before_stop'] is not None]
        if len(historical)<min_train+calibration_size: continue
        cal=historical[-calibration_size:];train=[r for r in historical[:-calibration_size] if r['label_end_index']<cal[0]['origin_index']-horizon]
        if len(train)<min_train: continue
        X=np.array([x[r['origin_index']] for r in train]);y=np.array([r['target_before_stop'] for r in train])
        C=np.array([x[r['origin_index']] for r in cal]);cy=np.array([r['target_before_stop'] for r in cal]);T=np.array([x[r['origin_index']] for r in test])
        raw=logistic(X,y,np.vstack([C,T]));adjusted=calibration_map(raw[:len(C)],cy,raw[len(C):])
        for r,p,pc in zip(test,raw[len(C):],adjusted):
            output.append(dict(r,probabilities={'historical_frequency':float(y.mean()),'logistic_fixed':float(p),'logistic_calibrated':float(pc)},
                training_label_end=max(t['label_end_index'] for t in train),calibration_start=cal[0]['origin_index'],
                calibration_label_end=max(t['label_end_index'] for t in cal),fold_test_start=test[0]['origin_index']))
    models={m:metrics(output,m) for m in ('historical_frequency','logistic_fixed','logistic_calibrated')}
    return {'model_version':VERSION,'kind':'historical_target_before_stop','horizon_bars':horizon,'cost_bps_round_trip':cost_bps,
            'dataset_sha256':hashlib.sha256(frame.to_csv().encode()).hexdigest(),'metrics':models,'predictions':output,
            'live_probability':None,'validation_status':'INSUFFICIENT VALIDATION — research only','promoted':False,
            'limitations':['Long only; fixed 1.5 ATR stop and 3 ATR target; next-open entry; opening beyond either barrier cancels.',
              'Same-bar target/stop order is unknowable: excluded from calibration, stop-first for net returns.',
              '20 bps default round-trip cost is an assumption, not measured spread; gap stops use opening price.',
              'Revised OHLC history is not point-in-time; no delisted universe, impact, dividends or execution guarantee.',
              'Probabilities shown only for historical test predictions; no production calibration claim.']}
