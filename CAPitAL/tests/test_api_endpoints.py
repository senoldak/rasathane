import pytest
from httpx import AsyncClient, ASGITransport
from capitolseeder.api.main import app
from capitolseeder.db.session import init_db
from capitolseeder.ingestion.congress_metadata import seed_congress_metadata

@pytest.mark.asyncio
async def test_api_endpoints():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trades endpoint
        res = await client.get("/api/v1/trades")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        
        # Leaderboard endpoint
        res = await client.get("/api/v1/politicians/leaderboard")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        
        # Bipartisan clusters endpoint
        res = await client.get("/api/v1/bipartisan-clusters")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        
        # Live conflicts endpoint
        res = await client.get("/api/v1/conflicts/live")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        
        # Violations endpoint
        res = await client.get("/api/v1/violations")
        assert res.status_code == 200
        data = res.json()
        assert "violations" in data
        assert "total_estimated_fines" in data

        # Simulation endpoint
        res = await client.get("/api/v1/simulate/shadow-portfolio")
        assert res.status_code == 200
        data = res.json()
        assert "portfolio_curve" in data
        assert "metrics" in data

        # Alerts webhook registration endpoint
        res = await client.post("/api/v1/alerts/webhook", json={"webhook_url": "https://discord.com/api/webhooks/test", "platform": "discord", "min_score": 80})
        assert res.status_code == 200
        assert res.json()["status"] == "registered"

@pytest.mark.asyncio
async def test_api_ssrf_protection():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Loopback URL
        res1 = await client.post("/api/v1/alerts/webhook", json={"webhook_url": "http://127.0.0.1:8000/hook", "platform": "discord"})
        assert res1.status_code == 400
        assert "ssrf protection" in res1.json()["detail"].lower()

        # Cloud metadata service URL
        res2 = await client.post("/api/v1/alerts/webhook", json={"webhook_url": "http://169.254.169.254/latest/meta-data", "platform": "slack"})
        assert res2.status_code == 400
        assert "ssrf protection" in res2.json()["detail"].lower()

@pytest.mark.asyncio
async def test_api_filtering_and_violations_totals():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. min_score filtering
        res = await client.get("/api/v1/trades?min_score=85")
        assert res.status_code == 200
        data = res.json()
        for item in data.get("items", []):
            assert item["composite_score"] >= 85.0

        # 2. alpha sort
        res_alpha = await client.get("/api/v1/trades?sort_by=alpha")
        assert res_alpha.status_code == 200
        alpha_items = res_alpha.json().get("items", [])
        if len(alpha_items) >= 2:
            assert (alpha_items[0].get("excess_return") or 0.0) >= (alpha_items[1].get("excess_return") or 0.0)

        # 3. Violations count decoupling from pagination limit
        res_viol = await client.get("/api/v1/violations?limit=1")
        assert res_viol.status_code == 200
        viol_data = res_viol.json()
        assert len(viol_data["violations"]) <= 1
        # total_violations_count must reflect all violations in DB, not just the single paginated item
        assert viol_data["total_violations_count"] >= len(viol_data["violations"])
