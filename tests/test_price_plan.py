import numpy as np
import pandas as pd
from kratos.price_plan import build_plan, describe, swing_levels
from kratos.technicals import indicators


def frame():
    c=100+np.sin(np.arange(100)/3)*5
    return pd.DataFrame({'Open':c-.2,'High':c+1,'Low':c-1,'Close':c,'Volume':1000.}, index=pd.bdate_range('2025-01-01',periods=100))


def test_levels_were_known_before_decision_bar():
    df=frame()
    levels=swing_levels(df)
    assert levels
    assert all(pd.Timestamp(x['known_at'])<df.index[-1] for x in levels)
    changed=df.copy();changed.iloc[-1,changed.columns.get_loc('High')]=9999
    assert swing_levels(changed)==levels


def test_prefix_plan_cannot_see_future_prices():
    df=frame();before=build_plan({'1D':df.iloc[:80]})
    df.iloc[80:,:4]*=10
    assert build_plan({'1D':df.iloc[:80]})==before


def test_breakout_is_not_immediate_entry_and_no_atr_targets():
    df=frame();df.iloc[-1]=[110,112,109,111,2000]
    p=build_plan({'1D':df},live_enough=True)
    assert p['timeframes']['1D']['state']=='BREAKOUT ATTEMPT'
    assert p['classification']=='WAIT' and not p['candidate']
    assert p['entry_zone'] is None and p['targets']==[] and p['ranges']=={}


def test_breakdown_avoids_new_long():
    df=frame();df.iloc[-1]=[90,91,87,88,2000]
    p=build_plan({'1D':df})
    assert p['classification']=='AVOID' and p['bias']=='DOWN'


def test_rejection_plan_has_real_resistance_and_stop_below_wick():
    df=frame();df.iloc[-1]=[95,99,93,98,2000]
    p=build_plan({'1D':df})
    assert p['entry_zone'] and p['stop']<93
    assert p['targets']
    observed={x['price'] for x in describe(df)['levels']}
    assert all(x in observed for x in p['targets'])
    assert p['targets'][0]>p['entry_zone'][1]>p['entry_zone'][0]>p['stop']
    assert p['probability'] is None


def test_relative_volume_excludes_signal_bar():
    df=frame();df.iloc[-1,df.columns.get_loc('Volume')]=10000
    assert indicators(df).VOL_RATIO.iloc[-1]==10


def test_missing_intraday_stays_unavailable():
    p=build_plan({'1D':frame()})
    assert p['timeframes']['1H']['state']=='UNAVAILABLE'


def test_invalid_candle_blocks_levels():
    df=frame();df.iloc[-1,df.columns.get_loc('High')]=1
    p=build_plan({'1D':df})
    assert p['entry_zone'] is None and p['targets']==[]
    assert p['timeframes']['1D']['state']=='UNAVAILABLE'
