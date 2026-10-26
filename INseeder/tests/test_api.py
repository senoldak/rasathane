import pytest
import pytest_asyncio
import os
import json
from fastapi.testclient import TestClient
from inseeder.db.database import Database
from inseeder.execution.paper_broker import PaperBroker
from inseeder.worker import IngestionWorker
from inseeder.api.app import create_app

@pytest.fixture
def app_and_client():
    test_db_path = "test_api.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    app = create_app(db_path=test_db_path)
    with TestClient(app) as client:
        yield app, client

    if os.path.exists(test_db_path):
        os.remove(test_db_path)

def test_get_trades_empty(app_and_client):
    app, client = app_and_client
    response = client.get("/api/trades")
    assert response.status_code == 200
    assert response.json() == []

def test_rules_endpoints(app_and_client):
    app, client = app_and_client
    # Create rule
    new_rule = {
        "name": "Test Rule",
        "is_active": 1,
        "min_score": 70,
        "min_value": 50000.0,
        "allowed_roles": ["CEO", "CFO"],
        "allowed_types": ["P"],
        "auto_execute": 0,
        "broker_target": "paper",
        "position_size_usd": 5000.0
    }
    create_resp = client.post("/api/rules", json=new_rule)
    assert create_resp.status_code == 201
    rule_id = create_resp.json()["id"]
    assert rule_id > 0

    # Get rules
    get_resp = client.get("/api/rules")
    assert get_resp.status_code == 200
    rules = get_resp.json()
    assert len(rules) == 1
    assert rules[0]["name"] == "Test Rule"

    # Delete rule
    del_resp = client.delete(f"/api/rules/{rule_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

def test_get_portfolio(app_and_client):
    app, client = app_and_client
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert "cash" in data
    assert "portfolio_value" in data
    assert "positions" in data

def test_order_execution_validation(app_and_client):
    app, client = app_and_client

    # Negative qty
    neg_resp = client.post("/api/orders/execute", json={
        "symbol": "AAPL",
        "qty": -10,
        "side": "buy",
        "price": 150.0
    })
    assert neg_resp.status_code == 422

    # Zero qty
    zero_resp = client.post("/api/orders/execute", json={
        "symbol": "AAPL",
        "qty": 0,
        "side": "buy",
        "price": 150.0
    })
    assert zero_resp.status_code == 422

    # Valid order
    valid_resp = client.post("/api/orders/execute", json={
        "symbol": "AAPL",
        "qty": 10,
        "side": "buy",
        "price": 150.0,
        "broker": "paper"
    })
    assert valid_resp.status_code == 200
    assert valid_resp.json()["status"] == "filled"

def test_rule_creation_validation(app_and_client):
    app, client = app_and_client

    # Invalid position_size_usd <= 0
    bad_rule = {
        "name": "Bad Rule",
        "min_score": 70,
        "min_value": 50000.0,
        "position_size_usd": -100.0
    }
    resp = client.post("/api/rules", json=bad_rule)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_hyperliquid_markets(app_and_client):
    from unittest.mock import AsyncMock, patch
    import httpx

    app, client = app_and_client
    db = app.state.db

    # Insert a sample trade for ticker 'PURR'
    await db.insert_trade({
        "accession_no": "0001-26-0001",
        "filing_date": "2026-09-20T10:00:00",
        "trade_date": "2026-09-20",
        "ticker": "PURR",
        "company_name": "Purr Token Inc",
        "insider_name": "Alice Officer",
        "insider_title": "CEO",
        "is_director": 1,
        "is_officer": 1,
        "is_ten_percent": 0,
        "transaction_code": "P",
        "shares": 1000.0,
        "price": 0.50,
        "value": 500.0,
        "shares_owned_after": 10000.0,
        "is_10b5_1": 0,
        "sec_url": "https://sec.gov/filing"
    })

    mock_universe = [{"name": "PURR", "maxLeverage": 50}]
    mock_contexts = [{"markPx": "0.52", "oraclePx": "0.51", "dayNtlVlm": "150000", "funding": "0.0001", "openInterest": "50000"}]

    mock_resp = httpx.Response(
        status_code=200,
        json=[{"universe": mock_universe}, mock_contexts],
        request=httpx.Request("POST", "https://api.hyperliquid.xyz/info")
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        resp = client.get("/api/hyperliquid/markets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["markets"][0]["symbol"] == "PURR"
        assert data["markets"][0]["insider_buy_count"] == 1
        assert data["markets"][0]["mark_price"] == 0.52

