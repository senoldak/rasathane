import pytest
from httpx import AsyncClient, ASGITransport
from bioseeder.api.main import app


@pytest.mark.asyncio
async def test_terminal_root_serving():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "biOF" in res.text
        assert "Cyber-Biotech" in res.text
        assert "Bio-Alpha" in res.text
