# tests/test_snapshot.py
from opsi.scan import run_snapshot
from opsi.store import init_db


def test_snapshot_writes_rows(monkeypatch, tmp_path):
    from opsi import scan

    db = str(tmp_path / "snap.db")
    init_db(db)
    monkeypatch.setattr(scan, "get_price", lambda s: 20.0)
    monkeypatch.setattr(
        scan,
        "get_chain",
        lambda s, right="P": [
            {
                "symbol": s,
                "expiry": "2026-10-16",
                "strike": 20.0,
                "bid": 0.5,
                "ask": 0.53,
                "lastPrice": 0.5,
                "volume": 100,
                "openInterest": 500,
            }
        ],
    )
    n = run_snapshot(db, symbols=["AAA", "BBB"])
    assert n == 2
    import sqlite3

    con = sqlite3.connect(db)
    rows = con.execute("SELECT symbol, close, stale_flag FROM universe_daily").fetchall()
    con.close()
    assert sorted(r[0] for r in rows) == ["AAA", "BBB"]
    assert all(r[1] == 20.0 and r[2] == 0 for r in rows)


def test_snapshot_stale_flag(monkeypatch, tmp_path):
    from opsi import scan

    db = str(tmp_path / "snap2.db")
    init_db(db)
    monkeypatch.setattr(scan, "get_price", lambda s: 20.0)
    monkeypatch.setattr(
        scan,
        "get_chain",
        lambda s, right="P": [
            {
                "symbol": s,
                "expiry": "2026-10-16",
                "strike": 20.0,
                "bid": 0.0,
                "ask": 0.0,
                "lastPrice": 0.05,
                "volume": 5,
                "openInterest": 10,
            }
        ],
    )
    assert run_snapshot(db, symbols=["ZZZ"]) == 1
    import sqlite3

    con = sqlite3.connect(db)
    flag = con.execute("SELECT stale_flag FROM universe_daily WHERE symbol='ZZZ'").fetchone()[0]
    con.close()
    assert flag == 1
