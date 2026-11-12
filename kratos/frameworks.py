"""Real upstream research engines. No training in HTTP request handlers."""
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import json
import numpy as np
import pandas as pd


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def frame(rows):
    from .data import tidy
    df = pd.DataFrame(rows).set_index('time').rename(columns=str.title)
    df.index = pd.to_datetime(df.index, utc=True)
    df = tidy(df)
    if len(df) < 80:
        raise ValueError('At least 80 completed daily bars required')
    return df


def vectorbt_research(rows):
    import vectorbt as vbt
    df = frame(rows)
    close = df.Close
    # Fixed rule, never optimized on these observations. Yesterday's close signal
    # executes at today's open, with separate costs on every fill.
    fast, slow = close.rolling(10).mean(), close.rolling(30).mean()
    entries = ((fast > slow) & (fast.shift() <= slow.shift())).shift(1, fill_value=False)
    exits = ((fast < slow) & (fast.shift() >= slow.shift())).shift(1, fill_value=False)
    pf = vbt.Portfolio.from_signals(close, entries, exits, price=df.Open,
        init_cash=10000, fees=0.001, slippage=0.0005, freq='1D')
    equity = pf.value()
    return {'status':'operational_historical', 'version':version('vectorbt'),
        'method':'Fixed 10/30-day moving-average crossover; next-session open execution',
        'total_return':float(pf.total_return()), 'max_drawdown':float(pf.max_drawdown()),
        'closed_trades':int(pf.trades.closed.count()),
        'win_rate':float(pf.trades.closed.win_rate()) if pf.trades.closed.count() else None,
        'equity':[{'time':str(i), 'value':float(v)} for i,v in equity.items()],
        'assumptions':{'initial_cash':10000,'fee_per_fill':0.001,'slippage_per_fill':0.0005},
        'limitations':['Historical illustration, not an independently validated strategy.',
            'Open positions marked to last close; hypothetical final exit cost not charged.',
            'Raw vendor prices; dividends excluded, revisions and corporate actions can distort results.',
            'Existing OB/FVG and liquidity diagnostics are custom Kratos code, not VectorBT features.']}


def qlib_research(rows, symbol):
    from qlib.contrib.model.linear import LinearModel
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.handler import DataHandlerLP
    df = frame(rows)
    close = df.Close
    features = pd.DataFrame({'return_1':close.pct_change(), 'return_5':close.pct_change(5),
        'volatility_10':close.pct_change().rolling(10).std(),
        'distance_ma20':close / close.rolling(20).mean() - 1})
    label = (close.shift(-1) / close - 1).rename('next_session_return')
    data = pd.concat({'feature':features, 'label':label.to_frame()}, axis=1).dropna()
    data.index = pd.MultiIndex.from_arrays([data.index.tz_localize(None), [symbol]*len(data)], names=['datetime','instrument'])
    # Expanding windows with a one-row embargo. Every prediction precedes its label.
    predictions=[]
    for start in range(40, len(data), 10):
        stop=min(start+10,len(data)); train_end=start-2
        handler=DataHandlerLP(data_loader={'class':'StaticDataLoader','module_path':'qlib.data.dataset.loader',
            'kwargs':{'config':data}}, infer_processors=[], learn_processors=[])
        dataset=DatasetH(handler=handler, segments={
            'train':(data.index[0][0],data.index[train_end][0]),
            'test':(data.index[start][0],data.index[stop-1][0])})
        model=LinearModel(estimator='ridge',alpha=1.0,fit_intercept=True)
        model.fit(dataset)
        for idx,pred in model.predict(dataset).items():
            predictions.append({'asof':idx[0].isoformat(),'predicted_return':float(pred),
                'actual_return':float(data.loc[idx,('label','next_session_return')]),
                'training_last_feature_date':data.index[train_end][0].isoformat()})
    if not predictions: raise ValueError('Insufficient held-out observations')
    actual=np.array([p['actual_return'] for p in predictions]); pred=np.array([p['predicted_return'] for p in predictions])
    mae=float(np.abs(actual-pred).mean()); baseline=float(np.abs(actual).mean())
    return {'status':'operational_historical', 'version':version('pyqlib'),
        'method':'Qlib DatasetH + LinearModel ridge; expanding 10-session test blocks; one-row embargo',
        'test_samples':len(predictions),'return_mae':mae,'no_change_mae':baseline,
        'skill_vs_no_change':1-mae/baseline if baseline else None,
        'direction_accuracy':float(((pred>0)==(actual>0)).mean()),'predictions':predictions,
        'limitations':['Small single-symbol revised-data experiment, not production forecasting.',
            'Features use completed bars only. No hyperparameter search or random split.',
            'Historical out-of-sample results are not forward-recorded accuracy or trading returns.',
            'No current forecast is issued from archived data.']}


def research_record(symbol, snapshot):
    rows=snapshot.get('technical',{}).get('candles',{}).get('1D',[])
    result={'symbol':symbol,'source':snapshot.get('provider'),
        'source_retrieved_at_utc':snapshot.get('retrieved_at_utc'),
        'data_last_session':snapshot.get('last_closed_bar_date'), 'input_sha256':fingerprint(rows),
        'calculated_at_utc':datetime.now(timezone.utc).isoformat(),'engines':{}}
    for key,run in [('vectorbt',lambda:vectorbt_research(rows)),('qlib',lambda:qlib_research(rows,symbol))]:
        try: result['engines'][key]=run()
        except Exception as exc:
            result['engines'][key]={'status':'unavailable','reason':type(exc).__name__+'; research did not complete'}
    for key,reason in {
        'openbb':'Not integrated: existing financial facts are Kratos provider output, not OpenBB. No verified statement feed or DCF model.',
        'tradingagents':'Not integrated: no authenticated, cost-approved AI inference endpoint has been verified.',
        'lean':'Not integrated: LEAN runtime and a compatible licensed data bundle have not been installed or tested.'}.items():
        result['engines'][key]={'status':'unavailable','reason':reason}
    return result
