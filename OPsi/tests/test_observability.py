# tests/test_observability.py
import logging
import sqlite3

from fastapi.testclient import TestClient

from opsi.api import app, get_db_path
from opsi.logging import get_scan_logger
from opsi.store import init_db


def test_scan_logger_includes_scan_id(caplog):
    log = get_scan_logger(42)
    with caplog.at_level(logging.INFO, logger="opsi.scan"):
        log.info("hello")
    assert caplog.records
    assert getattr(caplog.records[0], "scan_id", None) == "42"


def test_scan_records_metrics(monkeypatch, tmp_path):
    from opsi import scan

    db = str(tmp_path / "m.db")
    init_db(db)
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
                "lastPrice": 0.5,
                "volume": 200,
                "openInterest": 1000,
            }
        ],
    )
    sid = scan.run_full_scan(db, symbols=["AAA"])
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT status, duration_s, n_symbols, n_skipped, n_candidates FROM scans WHERE id=?",
        (sid,),
    ).fetchone()
    con.close()
    assert row[0] == "done"
    assert row[1] is not None and row[1] >= 0
    assert row[2] == 1
    assert row[3] == 0
    assert row[4] == 1


def test_health_endpoint(tmp_path):
    db = str(tmp_path / "h.db")
    init_db(db)
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        c = TestClient(app)
        r = c.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["last_scan_id"] is None
    finally:
        app.dependency_overrides.pop(get_db_path, None)


def test_health_with_scan(monkeypatch, tmp_path):
    from opsi import scan

    db = str(tmp_path / "h2.db")
    init_db(db)
    monkeypatch.setattr(scan, "get_price", lambda s: 99.0)  # prefilter hepsini eler
    monkeypatch.setattr(scan, "get_earnings_days", lambda s: None)
    sid = scan.run_full_scan(db, symbols=["AAA"])
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        body = TestClient(app).get("/api/health").json()
        assert body["last_scan_id"] == sid
        assert body["last_scan_status"] == "done"
        assert body["last_scan_candidates"] == 0
    finally:
        app.dependency_overrides.pop(get_db_path, None)
