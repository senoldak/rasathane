import pytest
from httpx import AsyncClient, ASGITransport
from capitolseeder.api.main import app
from capitolseeder.cli import run_seed

@pytest.mark.asyncio
async def test_full_platform_e2e():
    # 1. Run complete seed ingestion
    trades_seeded = await run_seed()
    assert trades_seeded >= 10
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 2. Check UI homepage serves the terminal shell
        ui_res = await client.get("/")
        assert ui_res.status_code == 200
        assert "CAPitAL" in ui_res.text
        
        # 3. Check trades API returns populated trades with scores
        trades_res = await client.get("/api/v1/trades")
        assert trades_res.status_code == 200
        trades_data = trades_res.json()
        assert len(trades_data["items"]) >= 10
        first_trade = trades_data["items"][0]
        assert first_trade["alpha_score"] is not None
        assert first_trade["alpha_score"]["composite_alpha_score"] > 0
        
        # 4. Check leaderboard returns ranked politicians
        lead_res = await client.get("/api/v1/politicians/leaderboard")
        assert lead_res.status_code == 200
        lead_data = lead_res.json()
        assert len(lead_data) >= 5
        
        # 5. Check live conflicts endpoint
        conf_res = await client.get("/api/v1/conflicts/live")
        assert conf_res.status_code == 200
        conf_data = conf_res.json()
        assert len(conf_data) > 0
        assert conf_data[0]["conflict_score"] >= 60.0

        # 6. Check bipartisan clusters endpoint
        clust_res = await client.get("/api/v1/bipartisan-clusters")
        assert clust_res.status_code == 200
        
        # 7. Check STOCK Act violations endpoint
        viol_res = await client.get("/api/v1/violations")
        assert viol_res.status_code == 200
        viol_data = viol_res.json()
        assert viol_data["total_violations_count"] >= 1

        # 8. Check shadow portfolio simulation endpoint
        sim_res = await client.get("/api/v1/simulate/shadow-portfolio")
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert "timeline" in sim_data
        assert "metrics" in sim_data
        assert sim_data["metrics"]["cumulative_return"] > 0
