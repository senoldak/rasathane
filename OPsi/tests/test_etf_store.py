# tests/test_etf_store.py
import sqlite3

from opsi.store import init_db, upsert_underlying


def test_underlyings_has_asset_type(tmp_path):
    db_file = str(tmp_path / "test.db")
    init_db(db_file)

    upsert_underlying(db_file, "SPY", 500.0, "2026-09-08T12:00:00", asset_type="etf")
    upsert_underlying(db_file, "AAPL", 220.0, "2026-09-08T12:00:00", asset_type="stock")

    with sqlite3.connect(db_file) as con:
        con.row_factory = sqlite3.Row
        spy = con.execute("SELECT * FROM underlyings WHERE symbol='SPY'").fetchone()
        assert spy["asset_type"] == "etf"
        aapl = con.execute("SELECT * FROM underlyings WHERE symbol='AAPL'").fetchone()
        assert aapl["asset_type"] == "stock"
