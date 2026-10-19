"""Conservative explainable rules, not statistical probabilities or trained ML."""
import math
from .technicals import finite


def propose_setup(t: dict, freshness: dict) -> dict:
    c, atr, ema, rsi = t["close"], t["atr"], t["ema20"], t["rsi"]
    trends = t["trends"]
    invalid = {"classification":"WAIT", "bias":"UNDETERMINED", "reasons":[],
               "entry_zone":None, "stop":None, "targets":[], "rr_to_resistance":None,
               "ranges":{}, "grade":"UNVALIDATED"}
    if not all(finite(v) and v > 0 for v in (c, atr, ema)) or not finite(rsi):
        invalid["reasons"].append("Insufficient validated indicators; no setup calculated.")
        return invalid
    # Published levels are derived only from last supplied CLOSED daily bars.
    # Stop below both the reference support and entry-zone floor.
    zone_lo = max(0.01, ema - 0.45 * atr)
    zone_hi = ema + 0.20 * atr
    entry = (zone_lo + zone_hi) / 2
    stop = max(0.01, min(t["support20"] - 0.20 * atr, entry - 1.50 * atr))
    risk = entry - stop
    targets = [entry + risk * k for k in (1.5, 2.5, 4)]
    r_to_res = (t["resistance60"] - entry) / risk if risk > 0 else None
    bullish = trends["1D"] == "UP" and trends["1W"] == "UP"
    bearish = trends["1D"] == "DOWN" and trends["1W"] == "DOWN"
    hourly_ok = trends["1H"] in ("UP", "MIXED")
    near_zone = abs(c - ema) <= 1.15 * atr
    vol = t["volume_ratio"]
    reasonable_volume = vol is not None and finite(vol) and vol >= 0.7
    reasons = []
    if bullish:
        reasons.append("Daily and weekly confirmed-bar trends are both up.")
    elif bearish:
        reasons.append("Daily and weekly confirmed-bar trends are both down.")
    else:
        reasons.append("Daily and weekly trends are not aligned.")
    if not hourly_ok:
        reasons.append("Hourly momentum is bearish or unavailable.")
    if not near_zone:
        reasons.append("Price is far from the 20-day reference entry area.")
    if not 42 <= rsi <= 70:
        reasons.append(f"RSI {rsi:.1f} is outside the preferred 42–70 range.")
    if not reasonable_volume:
        reasons.append("Current daily volume evidence is below threshold or unavailable.")
    if r_to_res is None or r_to_res < 1.5:
        reasons.append("Nearby 60-day supply offers <1.5R of room, or risk is undefined.")
    decision = "WAIT"
    if bearish and c < ema and rsi < 45:
        decision = "AVOID"
        reasons.append("Avoid new long entries in an aligned downtrend; not a short recommendation.")
    elif (bullish and hourly_ok and near_zone and 42 <= rsi <= 70 and
          reasonable_volume and r_to_res is not None and r_to_res >= 1.5 and
          freshness["live_enough"]):
        decision = "WAIT"
        reasons.append("Rule candidate only: no independent predictive validation exists, so the decision remains WAIT.")
    elif bullish:
        reasons.append("Bullish context, but at least one buy filter or live-data check failed.")
    if not freshness["live_enough"]:
        reasons.append("Minute price is not verified <=15 min during calendar-defined market hours. No live entry approval.")
    # Square-root-of-time ATR range is a heuristic sensitivity band, NOT a confidence interval.
    ranges = {str(n): {"lower":max(0.01, c - atr * math.sqrt(n)),
                         "upper":c + atr * math.sqrt(n)} for n in (5,20)}
    return {
        "classification":decision, "bias":"UP" if bullish else "DOWN" if bearish else "MIXED",
        "grade":"NO RELIABLE EDGE — INSUFFICIENT VALIDATION",
        "policies": {"Strict":{"grade":"UNVALIDATED","sample_size":0},
                     "Adaptive":{"grade":"UNVALIDATED","sample_size":0}},
        "scenarios": {
            "bull":f"Reconsider strength after a completed daily close above {t['resistance20'] if 'resistance20' in t else t['resistance60']:.2f}, then a successful retest. No timing or probability is established.",
            "base":"Follow the observed trend; wait for confirmation. ATR bands describe sensitivity, not expected prices.",
            "bear":f"A completed daily close below {t['support20']:.2f} weakens the support case. Gaps can bypass a stop."},
        "reasons":reasons, "entry_zone":(zone_lo, zone_hi), "stop":stop,
        "targets": targets, "rr_to_resistance":r_to_res,
        "ranges":ranges,
    }
