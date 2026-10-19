import numpy as np
import pandas as pd
from kratos.research import walk_forward

def frame():
    rng=np.random.default_rng(42)
    return pd.DataFrame({'Close':100*np.exp(np.cumsum(rng.normal(0,.01,600)))},index=pd.bdate_range('2023-01-01',periods=600))
def test_training_labels_are_purged_and_future_does_not_change_past_prediction():
    f=frame();r=walk_forward(f);first=r['forecasts'][0]
    assert all(p['last_training_target_index']<=p['origin_index']-5 for p in r['forecasts'])
    changed=f.copy();changed.iloc[first['origin_index']+1:,0]*=1.5
    r2=walk_forward(changed)
    assert first['predicted_returns']==r2['forecasts'][0]['predicted_returns']
    assert r['metrics']['no_change']['direction_accuracy'] is None
    assert not r['promoted']
