import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from capitolseeder.api.main import app
from capitolseeder.api.routers.websocket import ConnectionManager, manager
from capitolseeder.db.session import init_db

@pytest.mark.asyncio
async def test_connection_manager_logic():
    cm = ConnectionManager()
    assert len(cm.active_connections) == 0

    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()

    await cm.connect(mock_ws1)
    await cm.connect(mock_ws2)
    assert len(cm.active_connections) == 2
    mock_ws1.accept.assert_awaited_once()
    mock_ws2.accept.assert_awaited_once()

    # Broadcast to all
    await cm.broadcast({"type": "TEST", "data": 123})
    mock_ws1.send_text.assert_awaited_once()
    mock_ws2.send_text.assert_awaited_once()

    # Test dead connection cleanup
    mock_dead_ws = AsyncMock()
    mock_dead_ws.send_text.side_effect = RuntimeError("Broken pipe")
    await cm.connect(mock_dead_ws)
    assert len(cm.active_connections) == 3

    await cm.broadcast({"type": "TEST2"})
    assert mock_dead_ws not in cm.active_connections
    assert len(cm.active_connections) == 2

    cm.disconnect(mock_ws1)
    assert len(cm.active_connections) == 1
    cm.disconnect(mock_ws2)
    assert len(cm.active_connections) == 0

def test_websocket_endpoint_connection_and_ping():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/live-trades") as ws:
            # Immediate ACK message
            init_msg = ws.receive_json()
            assert init_msg["type"] == "CONNECTED"
            assert "CAPitAL Live Congressional Data Stream connected." in init_msg["message"]

            # Ping Pong
            ws.send_text("ping")
            pong_msg = ws.receive_text()
            assert pong_msg == "pong"

def test_websocket_broadcast_to_client():
    import asyncio

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/live-trades") as ws:
            init_msg = ws.receive_json()
            assert init_msg["type"] == "CONNECTED"

            # Broadcast through manager
            broadcast_payload = {
                "type": "NEW_TRADES",
                "count": 1,
                "trades": [{"ticker": "NVDA", "politician_name": "Nancy Pelosi"}]
            }
            asyncio.run(manager.broadcast(broadcast_payload))

            received = ws.receive_json()
            assert received["type"] == "NEW_TRADES"
            assert received["count"] == 1
            assert received["trades"][0]["ticker"] == "NVDA"

@pytest.mark.asyncio
async def test_manual_sync_endpoint():
    await init_db()
    with patch("capitolseeder.api.routers.trades.sync_live_congress_trades", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = 5
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/v1/trades/sync?limit=50")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert data["new_trades_count"] == 5
            assert "Ingested 5 new disclosure(s)" in data["message"]
            mock_sync.assert_awaited_once_with(limit=50)
