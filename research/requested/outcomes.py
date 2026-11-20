"""Settle eligible, pre-open requested forecasts alongside the nightly research run."""
import json
from pathlib import Path
from collections import defaultdict

import pandas as pd
from kratos.engine import analyze
from kratos.calendar import schedule
from kratos.forecast_outcomes import resolve
from scripts.publish_snapshot import pack
from datetime import timedelta

ROOT=Path("site/data/requested")


def run():
    due=defaultdict(list)
    for path in ROOT.glob("*/*/qlib.json"):
        if path.with_name("outcome.json").exists():
            continue
        record=json.loads(path.read_text())
        forecast=record["engines"]["qlib"].get("experimental_forecast")
        if not forecast:
            continue
        asof=pd.Timestamp(forecast["asof"]).date()
        sessions=schedule(record["symbol"],asof+timedelta(days=1),asof+timedelta(days=14))
        if sessions.empty:
            continue
        target=sessions.iloc[0]
        # Only forecasts issued before the target opened is eligible for scoring.
        if pd.Timestamp(record["calculated_at_utc"])>=target.market_open or pd.Timestamp.now(tz="UTC")<target.market_close:
            continue
        due[record["symbol"]].append((path,record))
    for symbol,records in due.items():
        try:
            payload=pack(symbol,analyze(symbol))
            for path,record in records:
                result=resolve(record,payload["technical"]["candles"]["1D"])
                if result:
                    result["source"]=payload["provider"]
                    result["source_retrieved_at_utc"]=payload["retrieved_at_utc"]
                    path.with_name("outcome.json").write_text(json.dumps(result,allow_nan=False,indent=2)+"\n")
        except Exception as exc:
            print("Outcome deferred",symbol,type(exc).__name__)


if __name__=="__main__":
    run()
