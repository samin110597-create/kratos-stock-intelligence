"""Closed-bar structural plans. Levels are chart observations, never probabilities.

Fixed specification: two-bar pivot confirmation, 0.15 ATR level buffer, 1.5R
minimum room after 20bp costs. No parameter selection on evaluation outcomes.
"""
import numpy as np
import pandas as pd
from .technicals import indicators, finite

VERSION = 'structure-plan-v1'


def swing_levels(frame):
    """Return levels known strictly BEFORE the latest decision bar."""
    out = []
    for i in range(2, len(frame)-3):
        for field, kind in [('High', 'swing high'), ('Low', 'swing low')]:
            value = float(frame[field].iloc[i])
            others = frame[field].iloc[i-2:i+3].drop(frame.index[i])
            if (value > others.max() if field == 'High' else value < others.min()):
                out.append({'price':value, 'kind':kind, 'formed_at':frame.index[i].isoformat(),
                            'known_at':frame.index[i+2].isoformat()})
    return out


def describe(frame):
    if frame is None or len(frame)<25:
        return {'state':'UNAVAILABLE', 'explanation':'Not enough completed bars.', 'levels':[]}
    frame = frame.tail(252)
    prices=frame[['Open','High','Low','Close']]
    if (not frame.index.is_unique or not frame.index.is_monotonic_increasing or
        not np.isfinite(prices.to_numpy()).all() or (prices<=0).any().any() or
        (frame.High<prices[['Open','Close','Low']].max(axis=1)).any() or
        (frame.Low>prices[['Open','Close','High']].min(axis=1)).any()):
        return {'state':'UNAVAILABLE','explanation':'Invalid or unordered completed candles.','levels':[]}
    row = indicators(frame).iloc[-1]
    close, atr = float(row.Close), float(row.ATR14)
    if not finite(atr) or atr<=0:
        return {'state':'UNAVAILABLE', 'explanation':'Price range is insufficient.', 'levels':[]}
    levels = swing_levels(frame)
    highs = [x for x in levels if x['kind']=='swing high']
    lows = [x for x in levels if x['kind']=='swing low']
    prior = frame.iloc[-21:-1]
    high, low = float(prior.High.max()), float(prior.Low.min())
    # Range edges are real fallbacks when no distinct swing has formed.
    for value, kind in [(high,'prior 20-bar high'),(low,'prior 20-bar low')]:
        levels.append({'price':value,'kind':kind,'formed_at':prior.index[-1].isoformat(),
                       'known_at':prior.index[-1].isoformat()})
    rising = len(highs)>1 and len(lows)>1 and highs[-1]['price']>highs[-2]['price'] and lows[-1]['price']>lows[-2]['price']
    falling = len(highs)>1 and len(lows)>1 and highs[-1]['price']<highs[-2]['price'] and lows[-1]['price']<lows[-2]['price']
    lower_sweep = row.Low<low and close>low
    upper_sweep = row.High>high and close<high
    if lower_sweep and upper_sweep: state, explanation = 'TWO-SIDED VOLATILITY', 'Both range edges were rejected; direction remains unclear.'
    elif close>high: state, explanation = 'BREAKOUT ATTEMPT', 'Closed above the prior range. A later hold or retest is still needed.'
    elif close<low: state, explanation = 'BREAKDOWN', 'Closed below the prior range; the broken floor is the first recovery hurdle.'
    elif lower_sweep: state, explanation = 'RECOVERY ATTEMPT', 'Undercut the prior low and recovered it by the close; a bottom is not yet confirmed.'
    elif upper_sweep: state, explanation = 'REJECTED AT RESISTANCE', 'Traded above the prior high but closed back below it.'
    elif rising and close>lows[-1]['price']: state, explanation = 'RISING', 'Confirmed swing highs and lows are rising.'
    elif falling and close<highs[-1]['price']: state, explanation = 'FALLING', 'Confirmed swing highs and lows are falling.'
    else: state, explanation = 'RANGE / TRANSITION', 'Confirmed swings do not establish a consistent direction.'
    # Deduplicate nearby levels; nearest first. Role is relative to current price.
    def nearest(side):
        candidates=sorted([z for z in levels if (z['price']<close if side=='support' else z['price']>close)],key=lambda z:abs(z['price']-close))
        selected=[]
        for z in candidates:
            if all(abs(z['price']-a['price'])>0.25*atr for a in selected): selected.append(z)
            if len(selected)==3: break
        return selected
    volume=frame.Volume.iloc[-21:-1]
    ratio=float(row.Volume/volume.mean()) if volume.notna().all() and volume.mean()>0 and finite(row.Volume) else None
    return {'state':state,'explanation':explanation,'asof':frame.index[-1].isoformat(),
            'close':close,'atr':atr,'support':nearest('support'),'resistance':nearest('resistance'),
            'prior_high':high,'prior_low':low,'volume_ratio':ratio,'levels':levels,
            'swing_high':highs[-1]['price'] if highs else None,'swing_low':lows[-1]['price'] if lows else None}


def build_plan(frames, *, live_enough=False):
    summaries={tf:describe(frames.get(tf)) for tf in ('15M','1H','4H','1D','1W')}
    d=summaries['1D']
    result={'model_version':VERSION,'classification':'WAIT','bias':'MIXED',
            'grade':'INSUFFICIENT VALIDATION','entry_zone':None,'stop':None,'targets':[],
            'rr_to_resistance':None,'ranges':{},'scenarios':{},'reasons':[],
            'timeframes':{tf:{k:v for k,v in summary.items() if k!='levels'} for tf,summary in summaries.items()},'setup_status':'NO CONFIRMED SETUP','candidate':False,
            'probability':None,'review_horizon':'Review after the next daily close; reassess after 5 sessions.',
            'validation':'Fixed chart rules; independent forecasting accuracy is not established.'}
    if d['state']=='UNAVAILABLE':
        result.update(summary='Not enough completed price history to build a plan.', next_action='Wait for sufficient data.')
        return result
    frame=frames['1D']; row=frame.iloc[-1]; c=d['close']; atr=d['atr']; buffer=0.15*atr
    supports=d['support']; resistances=d['resistance']
    support=supports[0]['price'] if supports else None
    resistance=resistances[0]['price'] if resistances else None
    upward=d['state'] in ('RISING','BREAKOUT ATTEMPT','RECOVERY ATTEMPT')
    downward=d['state'] in ('FALLING','BREAKDOWN','REJECTED AT RESISTANCE')
    result['bias']='UP' if upward else 'DOWN' if downward else 'MIXED'
    result['classification']='AVOID' if d['state'] in ('FALLING','BREAKDOWN') else 'WAIT'
    result['summary']=d['explanation']
    result['reasons']=[d['explanation']]
    # A retest requires a breakout on an EARLIER bar, followed by today's hold.
    older_high=float(frame.High.iloc[-22:-2].max()) if len(frame)>=26 else None
    retest=older_high is not None and frame.Close.iloc[-2]>older_high and row.Low<=older_high+buffer and c>older_high and c>row.Open
    rejection=support is not None and row.Low<=support+buffer and c>support+buffer and c>row.Open
    if retest or rejection:
        anchor=older_high if retest else support
        lo=max(anchor,c-0.25*atr); hi=c+0.10*atr
        stop=min(float(row.Low),anchor)-buffer
        targets=[z['price'] for z in resistances if z['price']>hi]
        # Never skip a nearby first obstacle to manufacture attractive reward/risk.
        if resistance is not None and resistance<=hi: targets=[]
        risk=hi-stop
        rr=(targets[0]-hi-0.002*hi)/(risk+0.002*hi) if targets and risk>0 else None
        volume_ok=d['volume_ratio'] is not None and d['volume_ratio']>=1.0
        higher_conflict=summaries['1W']['state'] in ('FALLING','BREAKDOWN')
        eligible=rr is not None and rr>=1.5 and volume_ok and not higher_conflict and not downward and stop>0
        result.update(entry_zone=[lo,hi],stop=stop,targets=targets,rr_to_resistance=rr,candidate=eligible,
                      setup_status=('RETEST HELD' if retest else 'SUPPORT REJECTION')+(' — RULE CANDIDATE' if eligible else ' — FILTERS NOT MET'))
        if rr is None: result['reasons'].append('No observed overhead target with usable room; no target is invented.')
        elif rr<1.5: result['reasons'].append('The first resistance offers less than 1.5 times the risk after assumed costs.')
        if not volume_ok: result['reasons'].append('Confirmation volume is missing or below its prior 20-bar average.')
        if higher_conflict: result['reasons'].append('The weekly structure is falling; this bounce conflicts with it.')
        result['next_action']=f'Only reassess inside {lo:.2f}–{hi:.2f}. Above {hi:.2f}, do not chase this plan. Below {stop:.2f}, this long thesis fails.'
    else:
        result['next_action']=(f'Wait for a daily close above {resistance:.2f}, then a later retest that holds.' if resistance else 'No overhead swing target is available. Wait for a new consolidation and retest.')
        if support: result['next_action']+=f' Alternatively, watch {support:.2f} for a bullish rejection confirmed by a daily close.'
    if not live_enough: result['reasons'].append('Use as a closed-bar plan; a recent executable price has not been verified.')
    if result['candidate']: result['reasons'].append('The chart rules qualify, but this is not a validated BUY signal.')
    result['scenarios']={
        'upside':('If price clears and holds '+f'{resistance:.2f}'+', the next observed hurdles are '+', '.join(f"{z['price']:.2f}" for z in resistances[1:])+'.' if len(resistances)>1 else 'No further observed overhead swing target is available; price discovery is unresolved.'),
        'downside':('If a daily close loses '+f'{support:.2f}'+', the next observed floors are '+', '.join(f"{z['price']:.2f}" for z in supports[1:])+'.' if len(supports)>1 else 'No lower confirmed swing floor is available in this lookback.'),
        'timing':'These are conditional paths, not arrival-date forecasts. Review the next daily close and cancel any untriggered plan after 5 sessions.'}
    return result
