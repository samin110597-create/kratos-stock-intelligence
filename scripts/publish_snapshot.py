"""Publish source-backed KRATOS analysis snapshots and forward forecast ledger.

Static Pages frontend reads these files. No invented prices, odds or backtests.
Runs in GitHub Actions; updates are observational, not real-time entitlements.
"""
import json
import math
import os
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from kratos.engine import analyze
from kratos.technicals import only_closed_daily

ET = ZoneInfo("America/Toronto")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
SNAPSHOTS = DATA / "snapshots.json"
LEDGER = DATA / "ledger.json"
DEFAULT = "NVDA,AVGO,AMAT,MU,CIFR,IREN,CRWV,NBIS,USAR,AXTI,GOOG,UBER"


def clean(v):
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            return clean(v.item())
        except (ValueError, TypeError):
            pass
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def iso_timestamp(idx):
    if len(idx) == 0:
        return None
    stamp = idx[-1]
    if getattr(stamp, "tzinfo", None) is None:
        return None
    return stamp.tz_convert("UTC").isoformat()


def pack(ticker, result):
    snap, tech, decision = result.snapshot, result.technical, result.decision
    df = tech["daily"]
    currency = snap.fundamentals.get("currency") or "USD"
    history = []
    for index, row in df.tail(120).iterrows():
        c = float(row["Close"])
        if math.isfinite(c):
            history.append({"date": str(index.date()), "close": round(c, 5)})
    return clean({
        "ticker": ticker,
        "provider": snap.provider,
        "currency": str(currency),
        "retrieved_at_utc": snap.retrieved_at.isoformat(),
        "minute_bar_utc": iso_timestamp(snap.minute.index),
        "price": tech["close"],
        "last_closed_bar_date": tech["asof_bar_date"],
        "freshness_at_build": result.freshness,
        "decision": decision,
        "technical": {
            "asof_bar_date": tech["asof_bar_date"],
            "trends": tech["trends"],
            "atr": tech["atr"], "rsi": tech["rsi"],
            "ema20": tech["ema20"], "ema50": tech["ema50"],
            "volume_ratio": tech["volume_ratio"],
            "support20": tech["support20"],
            "resistance20": tech["resistance20"],
            "resistance60": tech["resistance60"],
            "high52w": tech["high52w"], "low52w": tech["low52w"],
            "history": history
        },
        "fundamentals": {
            "facts": [{"label": k, "value": v} for k, v in result.facts],
            "valuation_note": result.valuation_note
        },
        "warnings": snap.warnings,
        "error": None
    })


def record_new(ledger, result, collected_at):
    snap, tech, dec = result.snapshot, result.technical, result.decision
    today = collected_at.astimezone(ET).date()
    bar_day = date.fromisoformat(tech["asof_bar_date"])
    if (today - bar_day).days > 5 or bar_day > today:
        return 0
    created = 0
    for horizon in (5, 20):
        key = "%s|%s|%s|rules-v1" % (snap.ticker, bar_day, horizon)
        if any(q.get("key") == key for q in ledger):
            continue
        band = dec.get("ranges", {}).get(str(horizon), {})
        ledger.append(clean({
            "key": key, "ticker": snap.ticker,
            "recorded_at_utc": collected_at.isoformat(),
            "source_bar_date": bar_day.isoformat(),
            "horizon_sessions": horizon,
            "base_close": tech["close"],
            "bias": dec["bias"], "classification": dec["classification"],
            "predicted_lower": band.get("lower"),
            "predicted_upper": band.get("upper"),
            "status": "OPEN", "outcome_date": None,
            "outcome_close": None, "direction_correct": None,
            "range_hit": None, "model_version": "rules-v1"
        }))
        created += 1
    return created


def resolve_existing(ledger, result, now):
    """Use only daily bars closed on a date after the recording DATE.

    Outcome cannot be a close that preceded the forecast. Preserve the
    original hypothesis, source bar and collection timestamp forever.
    """
    df = only_closed_daily(result.snapshot.daily, now=now)
    if df.empty:
        return 0
    df = df.copy()
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        df.index = idx.tz_convert(ET).tz_localize(None)
    count = 0
    for row in ledger:
        if row["ticker"] != result.snapshot.ticker or row["status"] != "OPEN":
            continue
        anchor = date.fromisoformat(row["source_bar_date"])
        record_date = datetime.fromisoformat(row["recorded_at_utc"]).astimezone(ET).date()
        minimum = max(anchor, record_date)
        later = df.loc[df.index.date > minimum]
        # Do not consider today's latest close before it can be independently
        # assumed final. For a completed Friday bar on Saturday this is fine.
        later = later.loc[later.index.date < now.astimezone(ET).date()]
        h = int(row["horizon_sessions"])
        if len(later) < h:
            continue
        outcome = later.iloc[h - 1]
        actual = float(outcome["Close"])
        if not math.isfinite(actual):
            continue
        bias = row["bias"]
        correct = (actual > row["base_close"] if bias == "UP" else
                   actual < row["base_close"] if bias == "DOWN" else None)
        lo, hi = row.get("predicted_lower"), row.get("predicted_upper")
        row["outcome_date"] = str(later.index[h-1].date())
        row["outcome_close"] = round(actual, 5)
        row["direction_correct"] = correct
        row["range_hit"] = bool(lo <= actual <= hi) if lo is not None and hi is not None else None
        row["status"] = "RESOLVED"
        row["resolved_at_utc"] = now.isoformat()
        count += 1
    return count


def audit(ledger):
    out = {"total": len(ledger), "resolved": 0, "direction_evaluated": 0,
           "direction_wins": 0, "range_evaluated": 0, "range_hits": 0,
           "by_horizon": {}, "recent": []}
    for h in (5, 20):
        group = [x for x in ledger if x.get("horizon_sessions") == h]
        done = [x for x in group if x["status"] == "RESOLVED"]
        directions = [x for x in done if x.get("direction_correct") is not None]
        ranged = [x for x in done if x.get("range_hit") is not None]
        part = {
            "total": len(group), "resolved": len(done),
            "direction_evaluated": len(directions),
            "direction_wins": sum(x["direction_correct"] is True for x in directions),
            "range_evaluated": len(ranged),
            "range_hits": sum(x["range_hit"] is True for x in ranged)
        }
        out["by_horizon"][str(h)] = part
        for k in ("resolved", "direction_evaluated", "direction_wins", "range_evaluated", "range_hits"):
            out[k] += part[k]
    for row in ledger[-25:][::-1]:
        out["recent"].append({
            k: row.get(k) for k in ("ticker", "recorded_at_utc", "horizon_sessions",
                                   "bias", "status", "direction_correct", "outcome_date")
        })
    return out


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(symbols=None, analyzer=analyze):
    symbols = symbols or [s.strip().upper() for s in os.getenv("KRATOS_SYMBOLS", DEFAULT).split(",") if s.strip()]
    previous = read_json(SNAPSHOTS, {"tickers": {}}).get("tickers", {})
    ledger = read_json(LEDGER, [])
    tickers = {}
    now = datetime.now(timezone.utc)
    success, new, resolved = 0, 0, 0
    for ticker in dict.fromkeys(symbols):
        try:
            print("Fetching", ticker, flush=True)
            result = analyzer(ticker)
            tickers[ticker] = pack(ticker, result)
            # Resolve old predictions BEFORE creating new ones.
            resolved += resolve_existing(ledger, result, now)
            new += record_new(ledger, result, now)
            success += 1
        except Exception as exc:
            detail = "%s: %s" % (type(exc).__name__, str(exc)[:220])
            print("ERROR", ticker, detail, flush=True)
            if ticker in previous and not previous[ticker].get("error"):
                old = previous[ticker].copy()
                old["warnings"] = list(old.get("warnings", [])) + ["LATEST REFRESH FAILED: " + detail]
                tickers[ticker] = old
            else:
                tickers[ticker] = {"ticker": ticker, "error": detail}
    write_json(LEDGER, ledger)
    write_json(SNAPSHOTS, {
        "generated_at_utc": now.isoformat(),
        "provider_note": "Yahoo Finance (unofficial); delayed/limited or unavailable; not a real-time market-data agreement.",
        "coverage": len(tickers), "fresh_results": success,
        "tickers": tickers, "audit": audit(ledger)
    })
    print("Published %d symbols, %d fetched, %d new forecasts, %d resolved" %
          (len(tickers), success, new, resolved), flush=True)


if __name__ == "__main__":
    run()
