"""Copy staged requests into Git, select the oldest outstanding work for each engine."""
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import urlopen
from datetime import date

ROOT = Path("site/data/requested")
ENGINES = ("qlib", "tradingagents", "lean")
SYMBOL = re.compile(r"[A-Z0-9^][A-Z0-9.^=_-]{0,19}")


def folder(symbol, session):
    if not SYMBOL.fullmatch(symbol) or date.fromisoformat(session).isoformat() != session:
        raise ValueError("Invalid request key")
    return ROOT / symbol / session


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n")


def collect():
    try:
        with urlopen("https://smit1105-kratos-backend.hf.space/api/research-inbox",timeout=40) as response:
            requests=json.load(response)["requests"]
    except Exception as exc:
        print("Space inbox unavailable; processing previously saved requests:", type(exc).__name__)
        requests=[]
    for r in requests[:256]:
        path=folder(r["symbol"],r["session"]) / "request.json"
        if not path.exists():
            save(path,{k:r[k] for k in ("symbol","session","created")})
    queue=sorted((json.loads(p.read_text()) for p in ROOT.glob("*/*/request.json")),key=lambda r:(r["created"],r["symbol"]))
    with open(os.environ["GITHUB_OUTPUT"],"a") as out:
        for engine in ENGINES:
            for r in queue:
                dest=folder(r["symbol"],r["session"])
                if (dest/(engine+".json")).exists():continue
                err=dest/(engine+"-failure.json")
                if err.exists():
                    e=json.loads(err.read_text())
                    if e["attempts"]>=3 or time.time()-e["attempted"]<3600:continue
                print(engine+"_symbol="+r["symbol"],file=out)
                print(engine+"_session="+r["session"],file=out)
                break


def finish(engine, successful):
    symbol=os.environ["RESEARCH_SYMBOL"]
    session=os.environ["REQUEST_SESSION"]
    dest=folder(symbol,session)
    name={"qlib":"current-research","lean":"lean-latest","tradingagents":"committee-latest"}[engine]
    if successful:
        record=json.loads(Path("site/data",name+".json").read_text())["tickers"][symbol]
        if record.get("symbol")!=symbol or record["engines"][engine]["status"]!="operational_historical" or record.get("refresh_failure"):
            raise ValueError("Missing completed result for this ticker")
        record={**record,"engines":{engine:record["engines"][engine]}}
        save(dest/(engine+".json"),record)
        return
    path=dest/(engine+"-failure.json")
    attempts=json.loads(path.read_text())["attempts"] if path.exists() else 0
    save(path,dict(attempts=attempts+1,attempted=int(time.time()),run=os.environ["GITHUB_RUN_ID"]))


if __name__=="__main__":
    if len(sys.argv)==1:collect()
    else:finish(sys.argv[1],sys.argv[2]=="success")
