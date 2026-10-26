# tests/test_etf_api.py
import sqlite3

from fastapi.testclient import TestClient

from opsi.api import app, get_db_path
from opsi.store import init_db, upsert_underlying


def test_api_returns_asset_type(tmp_path):
    db_file = str(tmp_path / "test.db")
    init_db(db_file)
    upsert_underlying(db_file, "SPY", 500.0, "2026-09-08T12:00:00", asset_type="etf")
    upsert_underlying(db_file, "AAPL", 220.0, "2026-09-08T12:00:00", asset_type="stock")

    with sqlite3.connect(db_file) as con:
        con.execute("INSERT INTO scans(id, status, n_candidates) VALUES(1, 'done', 2)")
        con.execute(
            "INSERT INTO contracts(id, symbol, expiry, strike, right, bid, ask) "
            "VALUES('C1', 'SPY', '2026-10-16', 490.0, 'P', 2.0, 2.2)"
        )
        con.execute(
            "INSERT INTO contracts(id, symbol, expiry, strike, right, bid, ask) "
            "VALUES('C2', 'AAPL', '2026-10-16', 210.0, 'P', 1.5, 1.7)"
        )
        con.execute(
            "INSERT INTO scores(scan_id, contract_id, strategy, score, ret_ann) "
            "VALUES(1, 'C1', 'csp', 85.0, 0.18)"
        )
        con.execute(
            "INSERT INTO scores(scan_id, contract_id, strategy, score, ret_ann) "
            "VALUES(1, 'C2', 'csp', 80.0, 0.15)"
        )
        con.commit()

    app.dependency_overrides[get_db_path] = lambda: db_file
    try:
        client = TestClient(app)

        resp_top5 = client.get("/api/top5")
        assert resp_top5.status_code == 200
        items_top5 = resp_top5.json()["items"]
        assert len(items_top5) == 2
        assert items_top5[0]["symbol"] == "SPY"
        assert items_top5[0]["asset_type"] == "etf"
        assert items_top5[1]["symbol"] == "AAPL"
        assert items_top5[1]["asset_type"] == "stock"

        resp_cand = client.get("/api/candidates?scan_id=1")
        assert resp_cand.status_code == 200
        items_cand = resp_cand.json()["items"]
        assert len(items_cand) == 2
        assert items_cand[0]["asset_type"] == "etf"
        assert items_cand[1]["asset_type"] == "stock"

        # Test asset_type='stock' filtering
        resp_stocks = client.get("/api/candidates?scan_id=1&asset_type=stock")
        assert resp_stocks.status_code == 200
        items_stocks = resp_stocks.json()["items"]
        assert len(items_stocks) == 1
        assert items_stocks[0]["symbol"] == "AAPL"
        assert items_stocks[0]["asset_type"] == "stock"

        # Test asset_type='etf' filtering
        resp_etfs = client.get("/api/candidates?scan_id=1&asset_type=etf")
        assert resp_etfs.status_code == 200
        items_etfs = resp_etfs.json()["items"]
        assert len(items_etfs) == 1
        assert items_etfs[0]["symbol"] == "SPY"
        assert items_etfs[0]["asset_type"] == "etf"
    finally:
        app.dependency_overrides.clear()
