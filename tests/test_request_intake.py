from concurrent.futures import ThreadPoolExecutor
from kratos.request_inbox import register, pending


def test_repeated_ticker_selections_share_one_ticket_per_session(tmp_path, monkeypatch):
    monkeypatch.setenv("KRATOS_INBOX", str(tmp_path/"queue.sqlite3"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert set(pool.map(lambda _: register("COST","2026-11-19"), range(12))) == {"received"}
    assert register("RY.TO","2026-11-19") == "received"
    assert register("COST","2026-11-20") == "received"
    assert {(r["symbol"],r["session"]) for r in pending()} == {
        ("COST","2026-11-19"),("RY.TO","2026-11-19"),("COST","2026-11-20")}
