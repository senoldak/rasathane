# tests/test_api.py
import sqlite3

from fastapi.testclient import TestClient

from opsi.api import app, get_db_path


def _client(db: str) -> TestClient:
    app.dependency_overrides[get_db_path] = lambda: db
    return TestClient(app)


def test_top5_empty():
    c = _client(":memory:")
    r = c.get("/api/top5")
    assert r.status_code in (200, 404)


def _seed_db(path: str, n_scores: int = 7, statuses=("done",)):
    from opsi.store import init_db

    init_db(path)
    con = sqlite3.connect(path)
    scan_ids = []
    for st in statuses:
        cur = con.execute(
            "INSERT INTO scans(started_at, status) VALUES (?, ?)",
            ("2026-09-08T00:00:00", st),
        )
        scan_ids.append(cur.lastrowid)
    sid = scan_ids[-1]
    for i in range(n_scores):
        cid = f"AAA|2026-10-16|{10 + i}"
        con.execute(
            "INSERT OR REPLACE INTO contracts(id,symbol,expiry,strike,right,bid,ask,volume,openInterest,iv,fetched_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                cid,
                "AAA",
                "2026-10-16",
                float(10 + i),
                "P",
                0.5,
                0.6,
                100,
                50,
                0.3,
                "2026-09-08T00:00:00",
            ),
        )
        con.execute(
            "INSERT OR REPLACE INTO scores(scan_id,contract_id,score,ret_ann,prob_otm,liq,iv_rank,trend,adj,details)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sid, cid, float(i), 0.1 * i, 0.9, 0.5, 0.5, 0.5, 0.0, "n"),
        )
    con.commit()
    con.close()
    return scan_ids


def test_top5_no_done_scan(tmp_path):
    db = str(tmp_path / "empty.db")
    _seed_db(db, n_scores=0, statuses=("running",))
    c = _client(db)
    r = c.get("/api/top5")
    assert r.status_code == 200
    body = r.json()
    assert body["as_of"] is None
    assert body["delayed"] is True
    assert body["items"] == []


def test_top5_with_data(tmp_path):
    db = str(tmp_path / "t.db")
    (sid,) = _seed_db(db, n_scores=7)
    c = _client(db)
    r = c.get("/api/top5", params={"scan_id": sid})
    assert r.status_code == 200
    body = r.json()
    assert body["delayed"] is True
    assert "15-min delayed data" in body["notice"]
    assert len(body["items"]) == 5
    scores = [it["score"] for it in body["items"]]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 6.0


def test_top5_latest_done_scan(tmp_path):
    db = str(tmp_path / "t2.db")
    sids = _seed_db(db, n_scores=0, statuses=("done", "done"))
    import sqlite3 as sl

    from opsi.store import save_scores

    con = sl.connect(db)
    con.execute(
        "INSERT OR REPLACE INTO contracts(id,symbol,expiry,strike,right,bid,ask,volume,openInterest,iv,fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("AAA|2026-10-16|10", "AAA", "2026-10-16", 10.0, "P", 0.5, 0.6, 100, 50, 0.3, "x"),
    )
    con.commit()
    con.close()
    save_scores(
        db, [(sids[0], "AAA|2026-10-16|10", "csp", 1.0, 0.1, 0.9, 0.5, 0.5, 0.5, 0.0, "n", "[]")]
    )
    save_scores(
        db, [(sids[1], "AAA|2026-10-16|10", "csp", 9.0, 0.2, 0.9, 0.5, 0.5, 0.5, 0.0, "n", "[]")]
    )
    con = sl.connect(db)
    con.execute("UPDATE scans SET n_candidates=1")
    con.commit()
    con.close()
    c = _client(db)
    r = c.get("/api/top5")
    assert r.status_code == 200
    body = r.json()
    assert body["as_of"] == sids[1]
    assert body["items"][0]["score"] == 9.0


def test_candidates_requires_scan_id(tmp_path):
    db = str(tmp_path / "t.db")
    _seed_db(db)
    c = _client(db)
    r = c.get("/api/candidates")
    assert r.status_code == 422


def test_candidates_limit(tmp_path):
    db = str(tmp_path / "t.db")
    (sid,) = _seed_db(db, n_scores=7)
    c = _client(db)
    r = c.get("/api/candidates", params={"scan_id": sid, "limit": 3})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 3
    r2 = c.get("/api/candidates", params={"scan_id": sid})
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 7


def test_index():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert "15-min delayed" in r.text
    assert "<div id=app>" in r.text
    assert "/static/app.js" in r.text
