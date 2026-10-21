"""Causal OHLCV research features; zones are patterns, not observed institutional orders."""
import pandas as pd
import numpy as np

def inspect(frame):
    if len(frame)<25:
        return {'status':'INSUFFICIENT DATA','events':[],'zones':[], 'probability':None}
    frame=frame.tail(250); c=frame.Close; last=frame.iloc[-1]
    prior_high=frame.High.shift(1).rolling(20).max().iloc[-1]
    prior_low=frame.Low.shift(1).rolling(20).min().iloc[-1]
    events=[]
    if last.Close>prior_high: events.append('Closed above prior 20-bar high')
    if last.Close<prior_low: events.append('Closed below prior 20-bar low')
    if last.High>prior_high and last.Close<prior_high: events.append('Failed breakout / upper sweep proxy')
    if last.Low<prior_low and last.Close>prior_low: events.append('Failed breakdown / lower sweep proxy')
    # A pivot is available only after TWO subsequent closed bars. Confirmation time is retained.
    highs=[]; lows=[]
    for i in range(2,len(frame)-2):
        part=frame.iloc[i-2:i+3]
        if frame.High.iloc[i]>part.High.drop(frame.index[i]).max():
            highs.append({'price':float(frame.High.iloc[i]),'pivot_at':frame.index[i].isoformat(),'confirmed_at':frame.index[i+2].isoformat()})
        if frame.Low.iloc[i]<part.Low.drop(frame.index[i]).min():
            lows.append({'price':float(frame.Low.iloc[i]),'pivot_at':frame.index[i].isoformat(),'confirmed_at':frame.index[i+2].isoformat()})
    hh = len(highs)>1 and highs[-1]['price']>highs[-2]['price']
    hl = len(lows)>1 and lows[-1]['price']>lows[-2]['price']
    lh = len(highs)>1 and highs[-1]['price']<highs[-2]['price']
    ll = len(lows)>1 and lows[-1]['price']<lows[-2]['price']
    structure='HH / HL' if hh and hl else 'LH / LL' if lh and ll else 'MIXED / INCOMPLETE PIVOTS'
    zones=[]
    for i in range(2,len(frame)):
        a,b=frame.iloc[i-2],frame.iloc[i]
        if b.Low>a.High: side,lo,hi='BULLISH FVG',float(a.High),float(b.Low)
        elif b.High<a.Low: side,lo,hi='BEARISH FVG',float(b.High),float(a.Low)
        else: continue
        later=frame.iloc[i+1:]
        overlap=(later.Low<=hi)&(later.High>=lo)
        bullish=side.startswith('BULL')
        invalid=(later.Close<lo) if bullish else (later.Close>hi)
        invalid_at=later.index[invalid][0].isoformat() if invalid.any() else None
        if invalid.any():
            later=later.loc[:later.index[invalid][0]]
            overlap=(later.Low<=hi)&(later.High>=lo)
        touches=int((overlap & ~overlap.shift(fill_value=False)).sum())
        penetration=(hi-later.Low.min())/(hi-lo) if bullish else (later.High.max()-lo)/(hi-lo)
        zones.append({'type':side,'lower':lo,'upper':hi,'created_at':frame.index[i].isoformat(),
                      'age_bars':len(frame)-1-i,'tests':touches,'fresh':touches==0,
                      'max_penetration_fraction':float(np.clip(penetration,0,1)) if len(later) else 0.,
                      'valid':not invalid.any(),'invalidated_at':invalid_at,
                      'creation_volume':float(b.Volume) if pd.notna(b.Volume) else None,
                      'evidence':'OHLCV pattern only; institutional orders UNKNOWN',
                      'hold_probability':None,'probability_status':'INSUFFICIENT DATA — PROBABILITY UNAVAILABLE',
                      'invalidation':'Closed bar below lower boundary' if bullish else 'Closed bar above upper boundary'})
    volume_ok=frame.Volume.tail(20).notna().all() and frame.Volume.tail(20).sum()>0
    vwap=float(((frame.High+frame.Low+frame.Close)/3*frame.Volume).tail(20).sum()/frame.Volume.tail(20).sum()) if volume_ok else None
    return {'status':'DESCRIPTIVE — NOT VALIDATED PREDICTIONS','structure':structure,
            'events':events,'structure_breaks':causal_breaks(frame)[-12:], 'session_vwap_proxy':session_vwap(frame), 'volume_participation_ratio':float(last.Volume/frame.Volume.iloc[-21:-1].mean()) if frame.Volume.iloc[-21:].notna().all() and frame.Volume.iloc[-21:-1].mean()>0 else None, 'confirmed_highs':highs[-3:],'confirmed_lows':lows[-3:], 'zones':zones[-12:],
            'rolling_20_bar_vwap_proxy':vwap,'vwap_note':'Typical-price weighted bar proxy; not tick VWAP or volume profile',
            'five_bar_return':float(c.iloc[-1]/c.iloc[-6]-1),
            'dollar_volume_proxy':float(last.Close*last.Volume) if pd.notna(last.Volume) else None,
            'probability':None}


def causal_breaks(frame):
    """Pivot levels become eligible two bars later; breaks use prior eligible levels."""
    high=low=None;broken_high=broken_low=None;trend=0;events=[]
    for i in range(4,len(frame)):
        # Exclude pivot confirmed on this very bar from its own break decision.
        previous=frame.Close.iloc[i-1];row=frame.iloc[i]
        if high is not None and high!=broken_high and previous<=high<row.Close:
            events.append({'bar':frame.index[i].isoformat(),'event':'BULLISH CHoCH' if trend==-1 else 'BULLISH BOS',
                           'level':float(high),'direction':'UP','confirmation':'Closed-bar crossing of previously confirmed pivot'})
            broken_high=high;trend=1
        if low is not None and low!=broken_low and previous>=low>row.Close:
            events.append({'bar':frame.index[i].isoformat(),'event':'BEARISH CHoCH' if trend==1 else 'BEARISH BOS',
                           'level':float(low),'direction':'DOWN','confirmation':'Closed-bar crossing of previously confirmed pivot'})
            broken_low=low;trend=-1
        k=i-2;part=frame.iloc[k-2:k+3]
        if frame.High.iloc[k]>part.High.drop(frame.index[k]).max(): high=float(frame.High.iloc[k])
        if frame.Low.iloc[k]<part.Low.drop(frame.index[k]).min(): low=float(frame.Low.iloc[k])
    return events


def session_vwap(frame):
    """OHLC typical-price proxy, resets each local trading date for intraday bars."""
    if len(frame)<2 or frame.index.tz is None: return None
    if frame.index.to_series().diff().dropna().min()>=pd.Timedelta(days=1): return None
    local=frame.index.tz_convert('America/Toronto');chunk=frame.loc[local.date==local[-1].date()]
    if chunk.Volume.isna().any() or chunk.Volume.sum()<=0: return None
    return float((((chunk.High+chunk.Low+chunk.Close)/3)*chunk.Volume).sum()/chunk.Volume.sum())
