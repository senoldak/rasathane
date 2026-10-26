# tests/test_store.py
import sqlite3

from opsi.store import init_db


def test_schema_created(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"underlyings", "contracts", "scans", "scores"} <= tables
