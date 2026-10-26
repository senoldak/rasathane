# tests/test_migration.py
import sqlite3

from opsi.store import init_db

OLD_SCHEMA = """
CREATE TABLE underlyings(symbol TEXT PRIMARY KEY, price REAL, updated_at TEXT);
CREATE TABLE contracts(id TEXT PRIMARY KEY, symbol TEXT, expiry TEXT, strike REAL, right TEXT, bid REAL, ask REAL, volume INTEGER, openInterest INTEGER, iv REAL, fetched_at TEXT);
CREATE TABLE scans(id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, status TEXT);
CREATE TABLE scores(scan_id INTEGER, contract_id TEXT, score REAL, ret_ann REAL, prob_otm REAL, liq REAL, iv_rank REAL, trend REAL, adj REAL, details TEXT, PRIMARY KEY(scan_id, contract_id));
"""


def test_init_db_migrates_old_schema(tmp_path):
    db = str(tmp_path / "old.db")
    con = sqlite3.connect(db)
    con.executescript(OLD_SCHEMA)
    con.execute("INSERT INTO scans(started_at, status) VALUES (?, ?)", ("x", "done"))
    con.execute(
        "INSERT INTO scores VALUES (?,?,?,?,?,?,?,?,?,?)",
        (1, "A|2026-10-16|10", 9.0, 0.1, 0.9, 0.5, 0.5, 0.5, 0.0, "n"),
    )
    con.commit()
    con.close()
    init_db(db)  # must not raise; backfills strategy + metrics cols
    con = sqlite3.connect(db)
    strat = con.execute("SELECT strategy FROM scores").fetchone()[0]
    assert strat == "csp"
    cols = [r[1] for r in con.execute("PRAGMA table_info(scans)").fetchall()]
    assert {"finished_at", "duration_s", "n_symbols", "n_skipped", "n_candidates"} <= set(cols)
    idx = con.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    assert ("idx_scores_scan_strategy",) in idx
    con.close()
