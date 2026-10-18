"""Causal market structure and gap research from CONFIRMED historical OHLCV bars.

No dealer-order inference: FVGs, liquidity sweeps and swing pivots are price
patterns, not identified institutional orders. All tests use local fixtures.
Callers must pass only FINALIZED bars, never a developing candle.
"""
from __future__ import annotations
import math
from typing import Any


def _finite(x):
    try:
        return math.isfinite(float(x))
    except (TypeError,ValueError):
        return False


def _pivots(data, field: str, *, left: int=2, right: int=2):
    """Pivot at i is only confirmed after bar i+right closes."""
    values=[float(v) for v in data[field]]
    out=[]
    for i in range(left,len(values)-right):
        current=values[i]
        others=values[i-left:i]+values[i+1:i+right+1]
        if field=="High" and current>max(others):
            out.append({"price":current,"date":str(data.index[i].date()),
                        "known_on":str(data.index[i+right].date())})
        if field=="Low" and current<min(others):
            out.append({"price":current,"date":str(data.index[i].date()),
                        "known_on":str(data.index[i+right].date())})
    return out


def causal_structure(completed_daily, *, breakout_lookback: int=20,
                     volume_confirmation: float=1.20) -> dict:
    """Classify last closed bar against ONLY the preceding bars.

    Rules:
    - prior reference highs/lows exclude the evaluated candle;
    - a sweep requires wick through a prior reference and close back inside;
    - a breakout requires CLOSE beyond prior range, with volume confirmation
      separately labeled; nothing is projected from unknown future bars;
    - pivot swings require two closed bars to the right of pivot;
    - FVGs are descriptive 3-bar gaps, with freshness computed from later
      known bars. Never interpret as institutional order-book evidence.
    """
    required={"Open","High","Low","Close","Volume"}
    if completed_daily is None or len(completed_daily)<max(25,breakout_lookback+3):
        return {"status":"INSUFFICIENT_BARS","reason":"Need at least 25 completed daily bars",
                "asof_date":None,"fvg":[]}
    if not required.issubset(completed_daily.columns):
        return {"status":"MISSING_OHLCV","reason":"Cannot calculate structure without OHLCV",
                "asof_date":None,"fvg":[]}
    df=completed_daily.sort_index().copy()
    h=df["High"].astype(float)
    l=df["Low"].astype(float)
    c=df["Close"].astype(float)
    o=df["Open"].astype(float)
    v=df["Volume"].astype(float)
    if not all(_finite(a) for a in [h.iloc[-1],l.iloc[-1],c.iloc[-1],o.iloc[-1]]):
        return {"status":"INVALID_PRICES","reason":"Latest completed bar has invalid price",
                "asof_date":str(df.index[-1].date()),"fvg":[]}
    if h.iloc[-1]<max(c.iloc[-1],o.iloc[-1]) or l.iloc[-1]>min(c.iloc[-1],o.iloc[-1]):
        return {"status":"INVALID_PRICES","reason":"Latest OHLC field contradicts high/low",
                "asof_date":str(df.index[-1].date()),"fvg":[]}
    prior_hi=float(h.iloc[-breakout_lookback-1:-1].max())
    prior_lo=float(l.iloc[-breakout_lookback-1:-1].min())
    close=float(c.iloc[-1])
    wick_hi=float(h.iloc[-1]);wick_lo=float(l.iloc[-1])
    volume_avg=float(v.iloc[-21:-1].mean())
    ratio=float(v.iloc[-1]/volume_avg) if volume_avg>0 and _finite(v.iloc[-1]) else None
    high_sweep=bool(wick_hi>prior_hi and close<=prior_hi)
    low_sweep=bool(wick_lo<prior_lo and close>=prior_lo)
    if low_sweep and not high_sweep:
        status="SELL_SIDE_SWEEP_RECLAIM"
        reason="Latest bar traded below prior 20-bar low but closed back above it."
    elif high_sweep and not low_sweep:
        status="BUY_SIDE_SWEEP_REJECTION"
        reason="Latest bar traded above prior 20-bar high but closed below it."
    elif high_sweep and low_sweep:
        status="BOTH_SIDES_SWEPT"
        reason="Latest bar swept both extremes: mixed intraday auction; no directional claim."
    elif close>prior_hi:
        status="CLOSE_ABOVE_PRIOR_HIGH"
        reason="Latest close above preceding 20-bar high; acceptance beyond one bar is unproven."
    elif close<prior_lo:
        status="CLOSE_BELOW_PRIOR_LOW"
        reason="Latest close below preceding 20-bar low; continuation unproven."
    else:
        status="INSIDE_PRIOR_RANGE"
        reason="Latest closed bar did not confirm a breakout or liquidity sweep."
    if ratio is None:
        participation="UNKNOWN"
    elif ratio>=volume_confirmation:
        participation="ABOVE_BASELINE"
    else:
        participation="NOT_CONFIRMED"
    swing_highs=_pivots(df,"High")
    swing_lows=_pivots(df,"Low")
    high_state=("HH" if swing_highs[-1]["price"]>swing_highs[-2]["price"] else "LH")
                if len(swing_highs)>=2 else "UNKNOWN"
    low_state=("HL" if swing_lows[-1]["price"]>swing_lows[-2]["price"] else "LL")
               if len(swing_lows)>=2 else "UNKNOWN"

    # True range average is evaluated using only known prior/current bars.
    tr=[max(float(h.iloc[j]-l.iloc[j]),abs(float(h.iloc[j]-c.iloc[j-1])),
            abs(float(l.iloc[j]-c.iloc[j-1]))) for j in range(1,len(df))]
    atr=sum(tr[-14:])/min(14,len(tr)) if tr else None
    fvg=[]
    for i in range(2,len(df)):
        gap_kind=None;low_bound=None;high_bound=None
        if float(l.iloc[i])>float(h.iloc[i-2]):
            gap_kind="BULLISH";low_bound=float(h.iloc[i-2]);high_bound=float(l.iloc[i])
        elif float(h.iloc[i])<float(l.iloc[i-2]):
            gap_kind="BEARISH";low_bound=float(h.iloc[i]);high_bound=float(l.iloc[i-2])
        if not gap_kind or atr is None or high_bound-low_bound < 0.2*atr:
            continue
        # A gap at i can be considered filled only by bars after i.
        following=df.iloc[i+1:]
        if len(following)==0:
            state="FRESH"
        elif gap_kind=="BULLISH":
            subsequent_low=float(following["Low"].min())
            state=("FILLED" if subsequent_low<=low_bound else
                   "PARTIAL" if subsequent_low<high_bound else "UNTOUCHED")
        else:
            subsequent_high=float(following["High"].max())
            state=("FILLED" if subsequent_high>=high_bound else
                   "PARTIAL" if subsequent_high>low_bound else "UNTOUCHED")
        if state!="FILLED":
            fvg.append({"kind":gap_kind,"low":round(low_bound,4),
                        "high":round(high_bound,4),
                        "created_on":str(df.index[i].date()),
                        "known_on":str(df.index[i].date()),"state":state,
                        "age_completed_bars":len(df)-i-1})
    return {
        "status":status,"reason":reason,
        "asof_date":str(df.index[-1].date()),
        "reference_high":round(prior_hi,4),"reference_low":round(prior_lo,4),
        "volume_ratio":round(ratio,3) if ratio is not None else None,
        "participation":participation,
        "confirmed_pivot_trend":{"highs":high_state,"lows":low_state},
        "last_confirmed_highs":swing_highs[-2:],
        "last_confirmed_lows":swing_lows[-2:],
        "fvg":fvg[-5:],
        "limitations":"Closed-bar PRICE patterns only. FVG is not proven institutional order flow. "
                      "Single-breakout close is not confirmed follow-through; no calibrated probability."
    }
