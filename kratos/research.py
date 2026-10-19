"""Fixed-spec expanding walk-forward experiment. Research only, never promotes a signal.

Inputs: revised provider daily prices, not point-in-time history. Label at origin i:
Close[i+h] / Close[i] - 1. All features known at close i. A training label must end
at or before i-h (an explicit h-session embargo). No test-driven parameter search.
"""
import hashlib
import numpy as np
import pandas as pd

SPEC='daily-return-walkforward-v1'
def features(close):
    daily=close.pct_change()
    return pd.DataFrame({'r1':daily,'r5':close.pct_change(5),'r20':close.pct_change(20),
                         'vol20':daily.rolling(20).std(),'ema_distance':close/close.ewm(span=20,adjust=False).mean()-1})

def walk_forward(frame,horizon=5,holdout=120,min_train=252):
    if horizon not in (5,20): raise ValueError('Only 5/20-session research horizons are implemented.')
    close=frame.Close.astype(float)
    if not np.isfinite(close).all() or (close<=0).any(): raise ValueError('Invalid research prices.')
    x=features(close).to_numpy();y=(close.shift(-horizon)/close-1).to_numpy()
    start=max(len(close)-holdout,min_train+20+2*horizon)
    forecasts=[]
    for i in range(start,len(close)-horizon,horizon):
        indices=np.arange(len(close))
        train=(indices+horizon<=i-horizon)&np.isfinite(x).all(axis=1)&np.isfinite(y)
        if train.sum()<min_train or not np.isfinite(x[i]).all(): continue
        X=x[train];Y=y[train];mean=X.mean(axis=0);scale=X.std(axis=0);scale[scale==0]=1
        z=(X-mean)/scale;design=np.column_stack([np.ones(len(z)),z]);penalty=np.eye(design.shape[1]);penalty[0,0]=0
        coef=np.linalg.solve(design.T@design+penalty,design.T@Y)
        ridge=float(np.r_[1,(x[i]-mean)/scale]@coef)
        models={'no_change':0.,'historical_mean':float(Y.mean()),'momentum':float(x[i,2]*horizon/20),
                'mean_reversion':float(-x[i,1]*horizon/5),'ridge_fixed_alpha_1':ridge}
        forecasts.append({'origin':str(frame.index[i].date()),'target':str(frame.index[i+horizon].date()),
                          'origin_index':i,'last_training_target_index':int(indices[train][-1]+horizon),
                          'actual_return':float(y[i]),'predicted_returns':models,'training_samples':int(train.sum())})
    metrics={}
    for model in ('no_change','historical_mean','momentum','mean_reversion','ridge_fixed_alpha_1'):
        pred=np.array([f['predicted_returns'][model] for f in forecasts]);actual=np.array([f['actual_return'] for f in forecasts]);directional=np.abs(pred)>1e-10
        metrics[model]={'samples':len(pred),'mae_return':float(np.abs(pred-actual).mean()) if len(pred) else None,
                        'rmse_return':float(np.sqrt(((pred-actual)**2).mean())) if len(pred) else None,
                        'directional_samples':int(directional.sum()),
                        'direction_accuracy':float((np.sign(pred[directional])==np.sign(actual[directional])).mean()) if directional.any() else None}
    base=metrics['no_change']['mae_return']
    for result in metrics.values(): result['mae_skill_vs_no_change']=1-result['mae_return']/base if base else None
    return {'spec':SPEC,'kind':'historical_walk_forward','horizon_sessions':horizon,'holdout_sessions':holdout,
            'dataset_sha256':hashlib.sha256(frame[['Close']].to_csv().encode()).hexdigest(),
            'data_start':str(frame.index[0].date()),'data_end':str(frame.index[-1].date()),'metrics':metrics,
            'forecasts':forecasts,'promoted':False,
            'limitations':['Single-symbol revised historical data; not survivorship-bias controlled.',
                           'No execution, spread, slippage or portfolio P&L is modeled.',
                           'Evaluation origins spaced one horizon apart; features remain correlated.',
                           'Fixed experimental specification; no model selected for production.',
                           'No fundamental/news features or calibrated price quantiles. Small samples are insufficient validation.']}
