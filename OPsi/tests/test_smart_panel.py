# tests/test_smart_panel.py
import contextlib
import sqlite3

from fastapi.testclient import TestClient

from opsi.api import app, get_db_path
from opsi.store import init_db


@contextlib.contextmanager
def _seed(tmp_path):
    db = str(tmp_path / "smart.db")
    init_db(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO scans(started_at, status, n_candidates) VALUES (?, ?, ?)",
        ("2026-09-08T00:00:00", "done", 5),
    )
    con.execute(
        "INSERT INTO scans(started_at, status, n_candidates) VALUES (?, ?, ?)",
        ("2026-09-09T00:00:00", "done", 0),
    )
    con.commit()
    con.close()
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        yield db
    finally:
        app.dependency_overrides.pop(get_db_path, None)


def test_top5_falls_back_to_latest_nonempty(tmp_path):
    with _seed(tmp_path):
        c = TestClient(app)
        r = c.get("/api/top5")
        assert r.status_code == 200
        body = r.json()
        assert body["as_of"] == 1
        assert body["as_of_is_latest"] is False


def test_top5_latest_nonempty_is_latest(tmp_path):
    with _seed(tmp_path):
        c = TestClient(app)
        con = sqlite3.connect(str(tmp_path / "smart.db"))
        con.execute(
            "INSERT INTO scans(started_at, status, n_candidates) VALUES (?, ?, ?)",
            ("2026-09-10T00:00:00", "done", 3),
        )
        con.commit()
        con.close()
        body = c.get("/api/top5").json()
        assert body["as_of"] == 3
        assert body["as_of_is_latest"] is True
