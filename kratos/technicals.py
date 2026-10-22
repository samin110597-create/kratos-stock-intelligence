"""Transparent, fixed-rule technical features. No look-ahead, no repaint."""
import math
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from .calendar import closed_bars, aggregate_intraday, weekly_closed, schedule


def indicators(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy().sort_index()
    if df.empty:
        return df
    c, h, lo = df["Close"], df["High"], df["Low"]
    df["EMA20"] = c.ewm(span=20, adjust=False, min_periods=20).mean()
    df["EMA50"] = c.ewm(span=50, adjust=False, min_periods=50).mean()
    df["EMA200"] = c.ewm(span=200, adjust=False, min_periods=200).mean()
    up = c.diff().clip(lower=0)
    down = -c.diff().clip(upper=0)
    ag = up.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = down.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = ag / al.replace(0, np.nan)
    rsi = 100 - 100/(1 + rs)
    rsi = rsi.mask((al == 0) & (ag > 0), 100).mask((ag == 0) & (al > 0), 0)
    df["RSI14"] = rsi.mask((ag == 0) & (al == 0), 50)
    tr = pd.concat([h-lo, (h-c.shift()).abs(), (lo-c.shift()).abs()], axis=1).max(axis=1)
    df["ATR14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    df["VOL20"] = df["Volume"].shift(1).rolling(20, min_periods=20).mean()
    df["VOL_RATIO"] = df["Volume"] / df["VOL20"].replace(0, np.nan)
    return df


def resample_ohlcv(df: pd.DataFrame, rule: str, *, four_hour: bool = False) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    if four_hour:
        # 09:30 ET alignment for intraday grouping, respecting daylight savings.
        if df.index.tz is not None:
            df = df.tz_convert("America/New_York")
        groups = df.resample(rule, origin="start_day", offset="9h30min")
    else:
        groups = df.resample(rule)
    return groups.agg({"Open":"first", "High":"max", "Low":"min", "Close":"last", "Volume":lambda s: s.sum() if s.notna().all() else np.nan}).dropna(subset=["Close"])


def normalize_daily_index(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if result.index.tz is not None:
        result.index = result.index.tz_convert("America/Toronto").tz_localize(None)
    return result


def only_closed_daily(raw, *, now=None, symbol='SPY'):
    return closed_bars(raw, '1d', now or datetime.now(ZoneInfo('UTC')), symbol)


def only_closed_hourly(raw, *, now=None, symbol='SPY'):
    return closed_bars(raw, '60min', now or datetime.now(ZoneInfo('UTC')), symbol)


def only_closed_weekly(raw_weekly, *, now=None, symbol='SPY'):
    return weekly_closed(raw_weekly, now or datetime.now(ZoneInfo('UTC')), symbol)


def trend_label(df: pd.DataFrame) -> str:
    if len(df) < 50:
        return "UNKNOWN"
    a = indicators(df).iloc[-1]
    if pd.isna(a["EMA50"]):
        return "UNKNOWN"
    if a["Close"] > a["EMA20"] > a["EMA50"]:
        return "UP"
    if a["Close"] < a["EMA20"] < a["EMA50"]:
        return "DOWN"
    return "MIXED"


def build_technicals(daily: pd.DataFrame, hourly: pd.DataFrame, *, quarter=None, symbol="SPY", now=None) -> dict:
    now = now or datetime.now(ZoneInfo("UTC"))
    daily = only_closed_daily(daily, now=now, symbol=symbol)
    hourly = only_closed_hourly(hourly, now=now, symbol=symbol)
    if len(daily) < 65:
        raise ValueError("Insufficient completed daily bars for trustworthy analysis.")
    d = indicators(daily)
    week = only_closed_weekly(resample_ohlcv(normalize_daily_index(daily), "W-FRI"), now=now, symbol=symbol)
    dates = set(normalize_daily_index(daily).index.normalize())
    week = week.loc[[all(day in dates for day in schedule(symbol, stamp-pd.Timedelta(days=4), stamp).index) for stamp in week.index]]
    four = aggregate_intraday(hourly, 240, 60, now, symbol)
    quarter = closed_bars(quarter, '15min', now, symbol) if quarter is not None else pd.DataFrame()
    last = d.iloc[-1]
    close = float(last["Close"])
    atr = float(last["ATR14"]) if pd.notna(last["ATR14"]) else None
    sup = float(d["Low"].tail(20).min())
    resistance = float(d["High"].tail(20).max())
    resistance60 = float(d["High"].tail(60).max())
    return {
        "close": close,
        "asof_bar_date": str(d.index[-1].date()),
        "daily": d,
        "atr": atr,
        "rsi": float(last["RSI14"]) if pd.notna(last["RSI14"]) else None,
        "ema20": float(last["EMA20"]) if pd.notna(last["EMA20"]) else None,
        "ema50": float(last["EMA50"]) if pd.notna(last["EMA50"]) else None,
        "volume_ratio": float(last["VOL_RATIO"]) if pd.notna(last["VOL_RATIO"]) else None,
        "support20": sup, "resistance20": resistance, "resistance60": resistance60,
        "trends": {"15M": trend_label(quarter), "1H": trend_label(hourly), "4H": trend_label(four),
                   "1D": trend_label(daily), "1W": trend_label(week)},
        "high52w": float(d["High"].tail(252).max()),
        "low52w": float(d["Low"].tail(252).min()),
        "bar_count": len(d),
        "frames": {"15M":quarter, "1H":hourly, "4H":four, "1D":daily, "1W":week},
        "signal_at_utc": pd.Timestamp(now).isoformat(),
    }


def finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
