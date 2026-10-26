import pytest
from unittest.mock import AsyncMock, patch
import httpx
from inseeder.execution.notifier import Notifier

@pytest.mark.asyncio
async def test_notifier_telegram_dispatch():
    notifier = Notifier(telegram_token="test_token", telegram_chat_id="12345")
    trade = {
        "ticker": "TSLA",
        "company_name": "Tesla Inc.",
        "insider_name": "Elon Musk",
        "insider_title": "CEO",
        "transaction_code": "P",
        "shares": 50000.0,
        "price": 250.0,
        "value": 12500000.0,
        "sec_url": "https://sec.gov/sample"
    }
    signal = {"score": 95, "cluster_count": 1}

    mock_resp = httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", "https://api.telegram.org"))
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        success = await notifier.send_signal_alert(signal, trade)
        assert success is True
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert "TSLA" in call_kwargs["json"]["text"]
        assert "95" in call_kwargs["json"]["text"]
        assert call_kwargs["json"]["parse_mode"] == "HTML"

@pytest.mark.asyncio
async def test_notifier_discord_dispatch():
    notifier = Notifier(discord_webhook_url="https://discord.com/api/webhooks/test")
    trade = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "insider_name": "Tim Cook",
        "insider_title": "CEO",
        "transaction_code": "P",
        "shares": 10000.0,
        "price": 200.0,
        "value": 2000000.0,
        "sec_url": "https://sec.gov"
    }
    signal = {"score": 85, "cluster_count": 2}

    mock_resp = httpx.Response(204, request=httpx.Request("POST", "https://discord.com"))
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        success = await notifier.send_signal_alert(signal, trade)
        assert success is True
        assert mock_post.called

@pytest.mark.asyncio
async def test_notifier_network_failure_safe():
    notifier = Notifier(telegram_token="fake", telegram_chat_id="123")
    trade = {"ticker": "XYZ", "transaction_code": "P", "value": 10000.0}
    signal = {"score": 70}

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ConnectError("Network Down")):
        success = await notifier.send_signal_alert(signal, trade)
        assert success is False # Must not raise exception
