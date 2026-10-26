from opsi.scan import load_universe
from opsi.store import init_db


def test_watchlist_narrows(tmp_path):
    init_db(str(tmp_path / "u.db"))
    wl = tmp_path / "wl.csv"
    wl.write_text("symbol\nAAA\nBBB\n", encoding="utf-8")
    out = load_universe(str(tmp_path / "u.db"), watchlist=str(wl))
    assert out == ["AAA", "BBB"]


def test_no_watchlist_falls_back(monkeypatch, tmp_path):
    from opsi import fetch

    db = str(tmp_path / "u2.db")
    init_db(db)
    monkeypatch.setattr(fetch, "get_sp500_symbols", lambda: ["AAA", "BBB", "CCC"])
    assert load_universe(db, universe="stocks") == ["AAA", "BBB", "CCC"]


def test_stale_skip(tmp_path):
    import sqlite3

    db = str(tmp_path / "u3.db")
    init_db(db)
    con = sqlite3.connect(db)
    for d in ("2026-09-06", "2026-09-07", "2026-09-08"):
        con.execute(
            "INSERT INTO universe_daily(symbol,date,close,iv_atm_30d,put_volume,put_oi,spread_sample,stale_flag)"
            " VALUES (?,?,?,?,?,?,?,?)",
            ("STALE", d, 20.0, 0.0, 0, 0, 0.0, 1),
        )
        con.execute(
            "INSERT INTO universe_daily(symbol,date,close,iv_atm_30d,put_volume,put_oi,spread_sample,stale_flag)"
            " VALUES (?,?,?,?,?,?,?,?)",
            ("FRESH", d, 20.0, 0.0, 100, 500, 0.05, 0),
        )
    con.commit()
    con.close()
    from opsi.scan import is_stale

    assert is_stale(db, "STALE") is True
    assert is_stale(db, "FRESH") is False
