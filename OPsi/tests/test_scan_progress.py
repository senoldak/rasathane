import time
from contextlib import contextmanager

from fastapi.testclient import TestClient

from opsi.api import app, get_db_path


@contextmanager
def _client_with_db(tmp_path):
    from opsi.store import init_db

    db = str(tmp_path / "progress.db")
    init_db(db)
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.pop(get_db_path, None)


def test_scan_active_idle(tmp_path):
    with _client_with_db(tmp_path) as (c, _db):
        r = c.get("/api/scans/active")
        assert r.status_code == 200
        assert r.json()["running"] is False


def test_scan_custom_returns_202_and_progress_completes(tmp_path, monkeypatch):
    import opsi.scan as scan_mod

    seen = {}

    def fake_run(db, *, symbols=None, universe="all", scan_id=None, progress_cb=None):
        seen.update(symbols=symbols, universe=universe, scan_id=scan_id)
        if progress_cb is not None:
            progress_cb(1, 1, (symbols or ["X"])[0])
        return scan_id

    monkeypatch.setattr(scan_mod, "run_full_scan", fake_run)
    with _client_with_db(tmp_path) as (c, _db):
        r = c.post("/api/scan-custom?symbols=SPY&symbols=QQQ")
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "ok"
        assert isinstance(body["scan_id"], int)
        assert body["symbols_count"] == 2
        deadline = time.time() + 10
        last = None
        while time.time() < deadline:
            last = c.get("/api/scans/active").json()
            if last["running"] is False:
                break
            time.sleep(0.2)
        assert last is not None and last["running"] is False
    assert seen["scan_id"] == body["scan_id"]
    assert seen["symbols"] == ["QQQ", "SPY"]


def test_pages_contain_scan_progress_bar():
    c = TestClient(app)
    for path in ("/panel", "/universes", "/lists", "/settings"):
        assert 'id="scan-progress"' in c.get(path).text


def test_static_app_js_polls_scan_progress():
    from pathlib import Path

    text = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("static", "app.js")
        .read_text(encoding="utf-8")
    )
    assert "scans/active" in text
    assert "setInterval(pollScanProgress, 2000)" in text
    assert "location.href = '/panel'" not in text
