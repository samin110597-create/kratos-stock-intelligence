import numpy as np
import pandas as pd
from kratos.target_paths import label_path,walk_forward_paths

def frame(n=1200):
    rng=np.random.default_rng(19);c=100*np.exp(np.cumsum(rng.normal(0,.01,n)))
    o=np.r_[c[0],c[:-1]];h=np.maximum(o,c)*1.006;l=np.minimum(o,c)*.994
    return pd.DataFrame({'Open':o,'High':h,'Low':l,'Close':c,'Volume':1000},index=pd.bdate_range('2020-01-01',periods=n))

def test_same_bar_collision_is_not_a_fabricated_win():
    f=frame();r=label_path(f,50)
    f.iloc[51,f.columns.get_loc('High')]=r['target']+1
    f.iloc[51,f.columns.get_loc('Low')]=r['stop']-1
    r=label_path(f,50)
    assert r['outcome']=='AMBIGUOUS' and r['target_before_stop'] is None and r['net_return']<0

def test_gap_stop_uses_actual_open_and_costs():
    f=frame();r=label_path(f,50)
    f.loc[f.index[51],['High','Low']]=[r['entry']+.01,r['entry']-.01]
    f.iloc[52,f.columns.get_loc('Open')]=r['stop']-5
    r=label_path(f,50)
    assert r['outcome']=='STOP'
    assert abs(r['net_return']-((r['stop']-5)/r['entry']-1-.002))<1e-10

def test_chronological_training_calibration_and_holdout():
    r=walk_forward_paths(frame(),min_train=30,calibration_size=15)
    assert r['predictions'] and r['live_probability'] is None
    for p in r['predictions']:
        assert p['training_label_end']<p['calibration_start']-5
        assert p['calibration_label_end']<p['fold_test_start']-5
        assert all(0<=v<=1 for v in p['probabilities'].values())

def test_future_mutation_cannot_change_earlier_prediction():
    f=frame();a=walk_forward_paths(f,min_train=30,calibration_size=15)
    origin=a['predictions'][0]['origin_index'];g=f.copy();g.iloc[origin+2:,:4]*=1.5
    b=walk_forward_paths(g,min_train=30,calibration_size=15)
    assert a['predictions'][0]['origin_index']==b['predictions'][0]['origin_index']
    for key,value in a['predictions'][0]['probabilities'].items():
        assert abs(value-b['predictions'][0]['probabilities'][key])<1e-12
