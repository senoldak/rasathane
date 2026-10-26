# tests/test_watchlists_api.py
from fastapi.testclient import TestClient

from opsi.api import app, get_db_path
from opsi.store import init_db


def test_watchlist_crud_and_custom_scan(tmp_path):
    db_file = str(tmp_path / "test_wl.db")
    init_db(db_file)

    app.dependency_overrides[get_db_path] = lambda: db_file
    client = TestClient(app)

    try:
        # 1. Başlangıçta boş olmalı
        res = client.get("/api/watchlists")
        assert res.status_code == 200
        assert res.json() == []

        # 2. Yeni liste oluştur
        res = client.post(
            "/api/watchlists", json={"name": "Teknoloji", "symbols": ["AAPL", "msft", "NVDA"]}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Teknoloji"
        assert sorted(data["symbols"]) == ["AAPL", "MSFT", "NVDA"]
        wl_id = data["id"]

        # 3. Listeleri getir
        res = client.get("/api/watchlists")
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["id"] == wl_id

        # 4. Aynı isimle ekleme hata vermeli (409 Conflict)
        res = client.post("/api/watchlists", json={"name": "Teknoloji", "symbols": ["AMD"]})
        assert res.status_code == 409

        # 5. Listeyi sil
        res = client.delete(f"/api/watchlists/{wl_id}")
        assert res.status_code == 200

        # Tekrar boş olmalı
        res = client.get("/api/watchlists")
        assert res.json() == []
    finally:
        app.dependency_overrides.clear()
