import pytest
import pytest_asyncio
import os
from inseeder.db.database import Database
from inseeder.execution.paper_broker import PaperBroker

@pytest_asyncio.fixture
async def paper_broker():
    test_db_path = "test_paper.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    db = Database(db_path=test_db_path)
    await db.init_db()
    broker = PaperBroker(db=db, initial_cash=100000.0)
    yield broker
    await db.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

@pytest.mark.asyncio
async def test_paper_buy_and_position(paper_broker):
    order = await paper_broker.submit_order(symbol="NVDA", qty=10, side="buy", price=120.0)
    assert order["status"] == "filled"
    assert order["fill_price"] == 120.0

    summary = await paper_broker.get_account_summary()
    assert summary["cash"] == 100000.0 - 1200.0
    assert summary["portfolio_value"] == 100000.0

    positions = await paper_broker.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "NVDA"
    assert positions[0]["qty"] == 10

@pytest.mark.asyncio
async def test_paper_sell_and_pnl(paper_broker):
    # Buy 10 @ $100
    await paper_broker.submit_order(symbol="AAPL", qty=10, side="buy", price=100.0)
    # Sell 5 @ $150
    sell_order = await paper_broker.submit_order(symbol="AAPL", qty=5, side="sell", price=150.0)
    assert sell_order["status"] == "filled"

    summary = await paper_broker.get_account_summary()
    # Initial: 100k - 1000 (buy) + 750 (sell) = 99750 cash
    assert summary["cash"] == 99750.0

    positions = await paper_broker.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"
    assert positions[0]["qty"] == 5

@pytest.mark.asyncio
async def test_insufficient_funds(paper_broker):
    order = await paper_broker.submit_order(symbol="BRK.A", qty=1, side="buy", price=700000.0)
    assert order["status"] == "rejected"
    assert "Insufficient" in order.get("reason", "")

@pytest.mark.asyncio
async def test_invalid_quantities(paper_broker):
    # Zero qty
    order_zero = await paper_broker.submit_order(symbol="AAPL", qty=0, side="buy", price=150.0)
    assert order_zero["status"] == "rejected"

    # Negative qty
    order_neg = await paper_broker.submit_order(symbol="AAPL", qty=-10, side="buy", price=150.0)
    assert order_neg["status"] == "rejected"

    # NaN qty
    order_nan = await paper_broker.submit_order(symbol="AAPL", qty=float("nan"), side="buy", price=150.0)
    assert order_nan["status"] == "rejected"

    # Inf qty
    order_inf = await paper_broker.submit_order(symbol="AAPL", qty=float("inf"), side="buy", price=150.0)
    assert order_inf["status"] == "rejected"

@pytest.mark.asyncio
async def test_cash_persistence_across_instances():
    test_db_path = "test_paper_persist.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    db = Database(db_path=test_db_path)
    await db.init_db()

    broker1 = PaperBroker(db=db, initial_cash=100000.0)
    await broker1.submit_order(symbol="MSFT", qty=10, side="buy", price=300.0)
    summary1 = await broker1.get_account_summary()
    assert summary1["cash"] == 97000.0

    # New broker instance on same DB should retain $97000.0 cash, NOT reset to $100000.0
    broker2 = PaperBroker(db=db, initial_cash=100000.0)
    summary2 = await broker2.get_account_summary()
    assert summary2["cash"] == 97000.0

    await db.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

