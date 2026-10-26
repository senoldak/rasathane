# tests/test_attribution_api.py
import sqlite3

from fastapi.testclient import TestClient

from opsi.api import app, get_db_path
from opsi.store import init_db


def _seed(tmp_path):
    db = str(tmp_path / "a.db")
    init_db(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO backtest_runs(started_at, scan_id, strategy, score_min, n, avg_return, win_rate, status, avg_score)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        ("2026-09-08T00:00:00", 1, "csp", 0.0, 10, 0.05, 0.8, "done", 85.0),
    )
    con.commit()
    con.close()
    return db


def test_attribution_buckets(tmp_path):
    db = _seed(tmp_path)
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        r = TestClient(app).get("/api/attribution", params={"strategy": "csp", "weeks": 12})
        assert r.status_code == 200
        body = r.json()
        assert [b["label"] for b in body["buckets"]] == ["70-80", "80-90", "90+"]
        assert body["buckets"][1]["n"] == 10  # avg_score=85 → 80-90 bandı
    finally:
        app.dependency_overrides.pop(get_db_path, None)


def test_attribution_empty(tmp_path):
    db = str(tmp_path / "e.db")
    init_db(db)
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        r = TestClient(app).get("/api/attribution")
        assert r.status_code == 200
        assert r.json()["buckets"] == []
    finally:
        app.dependency_overrides.pop(get_db_path, None)
