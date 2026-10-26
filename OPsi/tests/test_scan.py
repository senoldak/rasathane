# tests/test_scan.py
from opsi import scan


def test_scan_orders_by_final(monkeypatch, tmp_path):
    from opsi.store import init_db

    db = str(tmp_path / "s.db")
    init_db(db)
    monkeypatch.setattr(scan, "get_sp500_symbols", lambda: ["AAA"])
    monkeypatch.setattr(scan, "get_price", lambda s: 20.0)
    monkeypatch.setattr(scan, "get_earnings_days", lambda s: None)
    import datetime

    exp = (datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=20)).isoformat()
    monkeypatch.setattr(
        scan,
        "get_chain",
        lambda s, right="P": [
            {
                "symbol": s,
                "expiry": exp,
                "strike": 18.5,
                "bid": 0.5,
                "ask": 0.53,
                "volume": 200,
                "openInterest": 1000,
            },
            {
                "symbol": s,
                "expiry": exp,
                "strike": 35.0,
                "bid": 0.5,
                "ask": 0.53,
                "volume": 200,
                "openInterest": 1000,
            },
        ],
    )
    sid = scan.run_full_scan(db, symbols=["AAA"], strategies=["csp"])
    top = scan.top5(db, sid)
    assert len(top) == 1
    assert top[0]["strike"] == 18.5


def test_skip_counters_recorded(tmp_path):
    import sqlite3

    from opsi.store import init_db

    db = str(tmp_path / "counters.db")
    init_db(db)
    con = sqlite3.connect(db)
    cols = [r[1] for r in con.execute("PRAGMA table_info(scans)").fetchall()]
    con.close()
    assert "n_skip_stale" in cols
    assert "n_skip_price" in cols
    assert "n_empty_chain" in cols
