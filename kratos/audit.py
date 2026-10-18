"""Append-only forecasts; outcome updates never alter a published prediction.

Forecasts are evaluated at the Nth subsequently published DAILY bar. This is NOT an
intraday prediction engine and does not use an exchange holiday calendar.
"""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os
import sqlite3
from pathlib import Path
import pandas as pd

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS forecasts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 ticker TEXT NOT NULL,
 recorded_at_utc TEXT NOT NULL,
 source_bar_date TEXT NOT NULL,
 source_bar_utc TEXT,
 provider TEXT NOT NULL,
 horizon_sessions INTEGER NOT NULL CHECK(horizon_sessions IN (5,20)),
 base_close REAL NOT NULL,
 directional_bias TEXT NOT NULL,
 call TEXT NOT NULL,
 entry_low REAL,
 entry_high REAL,
 invalidation REAL,
 target_1 REAL,
 target_2 REAL,
 target_3 REAL,
 predicted_lower REAL,
 predicted_upper REAL,
 forecast_version TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'OPEN',
 outcome_bar_date TEXT,
 outcome_close REAL,
 direction_correct INTEGER,
 target_reached_on_end INTEGER,
 resolved_at_utc TEXT,
 UNIQUE(ticker, source_bar_date, horizon_sessions, forecast_version)
);
"""

def db_file() -> str:
    root = Path(os.getenv("KRATOS_DB_DIR", "data"))
    root.mkdir(parents=True, exist_ok=True)
    return str(root / "forecasts.sqlite3")


def connect(path: str | None = None):
    path = path or db_file()
    db = sqlite3.connect(path)
    db.execute("PRAGMA busy_timeout=5000")
    db.execute(CREATE_SQL)
    db.commit()
    return db


def record(ticker: str, t: dict, s: dict, provider: str, path: str | None = None) -> list[int]:
    """Record separate 5-session and 20-session hypotheses; no intraday signal claim."""
    created = datetime.now(timezone.utc)
    # Prevent historical cherry-picking / retrospective recording of old forecasts.
    bar_date = datetime.fromisoformat(t["asof_bar_date"]).date()
    age = (created.astimezone(ZoneInfo("America/Toronto")).date() - bar_date).days
    if age < 0 or age > 5:
        raise ValueError("Last completed daily bar is too old for a forward forecast. Try a fresh ticker/data source.")
    start = created.isoformat()
    zone = s["entry_zone"] or (None, None)
    targets = s.get("targets") or [None, None, None]
    added = []
    with connect(path) as db:
        for horizon in (5, 20):
            band = s.get("ranges", {}).get(str(horizon), {})
            data = (ticker, start, t["asof_bar_date"], provider, horizon, t["close"],
                    s["bias"], s["classification"], zone[0], zone[1], s.get("stop"),
                    *targets, band.get("lower"), band.get("upper"), "rules-v1")
            cur = db.execute("""INSERT OR IGNORE INTO forecasts
                (ticker, recorded_at_utc, source_bar_date, provider, horizon_sessions,
                 base_close, directional_bias, call, entry_low, entry_high,
                 invalidation, target_1, target_2, target_3,
                 predicted_lower, predicted_upper, forecast_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", data)
            if cur.rowcount:
                added.append(int(cur.lastrowid))
    return added


def _naive_trade_dates(daily: pd.DataFrame) -> pd.DataFrame:
    df = daily.copy().sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_convert("America/Toronto").tz_localize(None)
    df.index = df.index.normalize()
    return df.loc[~df.index.duplicated(keep="last")]


def resolve(ticker: str, daily: pd.DataFrame, path: str | None = None) -> int:
    """Only evaluate a forecast if its Nth FUTURE market bar is present.

    This evaluation can run whenever future data becomes available. Callout: for
    daily provider bars the latest trading day may still be forming. To prevent
    premature outcomes, the most recent bar is excluded unless today is NOT its
    date in ET; the previous day's final bar is always safe to use.
    """
    rows = _naive_trade_dates(daily)
    from zoneinfo import ZoneInfo
    today_et = datetime.now(ZoneInfo("America/Toronto")).date()
    rows = rows.loc[rows.index.date < today_et]
    resolved = 0
    with connect(path) as db:
        items = db.execute("""SELECT id, source_bar_date, horizon_sessions, base_close,
                directional_bias, target_1, recorded_at_utc FROM forecasts
                WHERE ticker=? AND status='OPEN'""", (ticker,)).fetchall()
        for rid, anchor, horizon, close, direction, target1, recorded_at in items:
            recorded_date = datetime.fromisoformat(recorded_at).astimezone(ZoneInfo("America/Toronto")).date()
            # Cannot "forecast" any trading close that was already in the past at recording.
            # Conservatively exclude the recording day: its close may already
            # have happened before a forecast was saved. This avoids same-day
            # look-ahead and defines horizons as *later* completed sessions.
            future = rows.loc[(rows.index > pd.Timestamp(anchor)) & (rows.index.date > recorded_date)]
            if len(future) < horizon:
                continue
            final = future.iloc[horizon-1]
            final_close = float(final["Close"])
            success = (final_close > close if direction == "UP" else
                       final_close < close if direction == "DOWN" else None)
            target_hit = int(final_close >= target1) if target1 is not None and direction == "UP" else None
            db.execute("""UPDATE forecasts SET status='RESOLVED', outcome_bar_date=?,
                outcome_close=?, direction_correct=?, target_reached_on_end=?,
                resolved_at_utc=? WHERE id=? AND status='OPEN'""",
                (str(future.index[horizon-1].date()), final_close,
                 None if success is None else int(success), target_hit,
                 datetime.now(timezone.utc).isoformat(), rid))
            resolved += 1
    return resolved


def recent_records(path: str | None = None, limit: int = 100):
    with connect(path) as db:
        rows = db.execute("""SELECT ticker, source_bar_date, horizon_sessions,
            directional_bias, call, ROUND(base_close,3), status,
            outcome_bar_date, ROUND(outcome_close,3), direction_correct,
            predicted_lower, predicted_upper
            FROM forecasts ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
    return rows


def audit_stats(path: str | None = None) -> dict:
    with connect(path) as db:
        rows = db.execute("""SELECT horizon_sessions,
            COUNT(*) AS n, SUM(CASE WHEN status='RESOLVED' THEN 1 ELSE 0 END) AS done,
            SUM(CASE WHEN direction_correct=1 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN direction_correct IN (0,1) THEN 1 ELSE 0 END) AS evaluated,
            SUM(CASE WHEN status='RESOLVED' AND outcome_close BETWEEN predicted_lower AND predicted_upper
                     THEN 1 ELSE 0 END) AS range_hits
            FROM forecasts GROUP BY horizon_sessions ORDER BY horizon_sessions""").fetchall()
    return {int(h): {"total":n,"resolved":done,"direction_wins":wins or 0,
                     "direction_evaluated":evaluated or 0,"range_hits":range_hits or 0}
            for h,n,done,wins,evaluated,range_hits in rows}
