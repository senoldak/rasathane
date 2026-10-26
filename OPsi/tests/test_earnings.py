# tests/test_earnings.py
import datetime

import pandas as pd

from opsi import fetch


class _FakeTicker:
    def __init__(self, *a, **k):
        pass

    @property
    def calendar(self):
        future = datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=5)
        return pd.DataFrame({"Earnings Date": [pd.Timestamp(future)]})


def test_earnings_days_counts(monkeypatch):
    monkeypatch.setattr(fetch.yf, "Ticker", _FakeTicker)
    assert fetch.get_earnings_days("AAA") == 5


def test_earnings_missing_calendar(monkeypatch):
    class T(_FakeTicker):
        @property
        def calendar(self):
            return pd.DataFrame()

    monkeypatch.setattr(fetch.yf, "Ticker", T)
    assert fetch.get_earnings_days("AAA") is None


def test_upsert_preserves_earnings_cache(tmp_path):
    import sqlite3

    from opsi.store import init_db, upsert_underlying

    db = str(tmp_path / "e.db")
    init_db(db)
    upsert_underlying(db, "AAA", 10.0, "2026-09-08T00:00:00", "2026-09-20")
    upsert_underlying(db, "AAA", 11.0, "2026-09-08T00:00:01")  # earnings_date yok
    con = sqlite3.connect(db)
    row = con.execute("SELECT price, earnings_date FROM underlyings WHERE symbol='AAA'").fetchone()
    con.close()
    assert row[0] == 11.0
    assert row[1] == "2026-09-20"


def test_past_earnings_no_penalty(monkeypatch, tmp_path):
    from opsi import scan
    from opsi.store import init_db

    db = str(tmp_path / "p.db")
    init_db(db)
    monkeypatch.setattr(scan, "get_earnings_days", lambda s: -3)
    import datetime

    exp = (datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=20)).isoformat()
    monkeypatch.setattr(scan, "get_price", lambda s: 20.0)
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
            }
        ],
    )
    sid = scan.run_full_scan(db, symbols=["AAA"], strategies=["csp"])
    assert scan.top5(db, sid) != []


def test_stale_future_fresh_none_clears_cache(monkeypatch, tmp_path):
    import sqlite3

    from opsi import scan
    from opsi.store import init_db, upsert_underlying

    db = str(tmp_path / "s.db")
    init_db(db)
    today = datetime.datetime.now(datetime.UTC).date()
    stale = (today + datetime.timedelta(days=3)).isoformat()
    upsert_underlying(db, "AAA", 20.0, "2000-01-01T00:00:00", stale)
    monkeypatch.setattr(scan, "get_earnings_days", lambda s: None)
    monkeypatch.setattr(scan, "get_price", lambda s: 20.0)
    exp = (today + datetime.timedelta(days=20)).isoformat()
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
            }
        ],
    )
    sid = scan.run_full_scan(db, symbols=["AAA"], strategies=["csp"])
    con = sqlite3.connect(db)
    cached = con.execute("SELECT earnings_date FROM underlyings WHERE symbol='AAA'").fetchone()
    con.close()
    assert cached[0] == ""
    assert scan.top5(db, sid) != []
