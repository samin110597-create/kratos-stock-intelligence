"""Bounded staging for verified ticker/session requests until GitHub picks them up."""
from pathlib import Path
import os
import sqlite3
import time


def inbox():
    path = Path(os.getenv("KRATOS_INBOX", "/tmp/kratos-research-requests.sqlite3"))
    db = sqlite3.connect(path, timeout=3)
    db.execute("CREATE TABLE IF NOT EXISTS tickets(symbol TEXT, session TEXT, created INTEGER, PRIMARY KEY(symbol,session))")
    return db


def register(symbol, session):
    from contextlib import closing
    with closing(inbox()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM tickets WHERE created < ?", (int(time.time())-7*86400,))
        key = (symbol, session)
        if not db.execute("SELECT 1 FROM tickets WHERE symbol=? AND session=?", key).fetchone():
            if db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] >= 256:
                return "full"
            db.execute("INSERT INTO tickets VALUES(?,?,?)", (*key, int(time.time())))
        return "received"


def pending():
    from contextlib import closing
    with closing(inbox()) as db:
        return [dict(symbol=s, session=d, created=t) for s,d,t in db.execute(
            "SELECT symbol,session,created FROM tickets WHERE created>=? ORDER BY created,symbol",
            (int(time.time())-7*86400,))]
