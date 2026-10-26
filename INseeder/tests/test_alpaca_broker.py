import pytest
from unittest.mock import AsyncMock, patch
import httpx
from inseeder.execution.alpaca_broker import AlpacaBroker

@pytest.mark.asyncio
async def test_alpaca_get_account_summary():
    broker = AlpacaBroker(
        api_key="test_key",
        api_secret="test_secret",
        base_url="https://paper-api.alpaca.markets"
    )

    mock_resp = httpx.Response(200, json={
        "cash": "50000.00",
        "portfolio_value": "75000.00",
        "buying_power": "100000.00"
    }, request=httpx.Request("GET", "https://paper-api.alpaca.markets/v2/account"))

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        summary = await broker.get_account_summary()
        assert summary["broker"] == "alpaca"
        assert summary["cash"] == 50000.0
        assert summary["portfolio_value"] == 75000.0

@pytest.mark.asyncio
async def test_alpaca_submit_market_order():
    broker = AlpacaBroker(
        api_key="test_key",
        api_secret="test_secret",
        base_url="https://paper-api.alpaca.markets"
    )

    mock_resp = httpx.Response(200, json={
        "id": "alpaca_order_123",
        "symbol": "NVDA",
        "qty": "10",
        "side": "buy",
        "status": "accepted",
        "type": "market"
    }, request=httpx.Request("POST", "https://paper-api.alpaca.markets/v2/orders"))

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        order = await broker.submit_order(symbol="NVDA", qty=10, side="buy")
        assert order["status"] == "accepted"
        assert order["symbol"] == "NVDA"
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["symbol"] == "NVDA"
        assert call_kwargs["json"]["qty"] == "10"
        assert call_kwargs["json"]["side"] == "buy"
