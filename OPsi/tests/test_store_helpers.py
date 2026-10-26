# tests/test_store_helpers.py
import sqlite3

from opsi.store import create_scan, init_db, insert_contracts, save_scores, upsert_underlying


def test_helpers_roundtrip(tmp_path):
    db = str(tmp_path / "h.db")
    init_db(db)
    upsert_underlying(db, "F", 14.5, "2026-09-08T00:00:00")
    upsert_underlying(db, "F", 14.6, "2026-09-08T00:00:01")
    insert_contracts(
        db,
        [
            ("F|2026-10-16|13", "F", "2026-10-16", 13.0, "P", 0.0, 0.0, 100, 500, 0.3, "x"),
        ],
    )
    sid = create_scan(db, "2026-09-08T00:00:00")
    assert sid == 1
    save_scores(
        db, [(sid, "F|2026-10-16|13", "csp", 50.0, 0.1, 0.9, 0.5, 0.5, 0.5, 1.0, "n", "[]")]
    )
    con = sqlite3.connect(db)
    assert con.execute("SELECT price FROM underlyings WHERE symbol='F'").fetchone()[0] == 14.6
    assert con.execute("SELECT COUNT(*) FROM contracts").fetchone()[0] == 1
    assert con.execute("SELECT score FROM scores").fetchone()[0] == 50.0
    idx = con.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    assert ("idx_scores_scan_score",) in idx
    plan = con.execute(
        "EXPLAIN QUERY PLAN SELECT s.score FROM scores s WHERE s.scan_id=1 ORDER BY s.score DESC LIMIT 5"
    ).fetchall()
    assert not any("TEMP B-TREE" in str(r) for r in plan)
    con.close()
