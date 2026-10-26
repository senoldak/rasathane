import pytest
import pytest_asyncio
import os
from inseeder.db.database import Database

@pytest_asyncio.fixture
async def db():
    test_db_path = "test_inseeder.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    database = Database(db_path=test_db_path)
    await database.init_db()
    yield database
    await database.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

@pytest.mark.asyncio
async def test_insert_and_get_trade(db):
    trade_data = {
        "accession_no": "0001193125-24-000001",
        "filing_date": "2026-09-20T18:00:00",
        "trade_date": "2026-09-19",
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "insider_name": "Tim Cook",
        "insider_title": "CEO",
        "is_director": 1,
        "is_officer": 1,
        "is_ten_percent": 0,
        "transaction_code": "P",
        "shares": 50000.0,
        "price": 220.0,
        "value": 11000000.0,
        "shares_owned_after": 3200000.0,
        "is_10b5_1": 0,
        "sec_url": "https://www.sec.gov/Archives/edgar/data/sample.xml"
    }
    trade_id = await db.insert_trade(trade_data)
    assert trade_id > 0
    trades = await db.get_trades(limit=10)
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"
    assert trades[0]["insider_name"] == "Tim Cook"

@pytest.mark.asyncio
async def test_rules_crud(db):
    rule_data = {
        "name": "High Conviction CEO Buys",
        "is_active": 1,
        "min_score": 75,
        "min_value": 100000.0,
        "allowed_roles": '["CEO"]',
        "allowed_types": '["P"]',
        "auto_execute": 1,
        "broker_target": "paper",
        "position_size_usd": 5000.0
    }
    rule_id = await db.insert_rule(rule_data)
    assert rule_id > 0
    rules = await db.get_rules()
    assert len(rules) == 1
    assert rules[0]["name"] == "High Conviction CEO Buys"

@pytest.mark.asyncio
async def test_duplicate_trade_and_trade_exists(db):
    trade_data = {
        "accession_no": "0001193125-24-000099",
        "filing_date": "2026-09-20T18:00:00",
        "trade_date": "2026-09-19",
        "ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "insider_name": "Satya Nadella",
        "insider_title": "CEO",
        "transaction_code": "P",
        "shares": 1000.0,
        "price": 400.0,
        "value": 400000.0,
    }
    assert await db.trade_exists("0001193125-24-000099") is False

    trade_id1 = await db.insert_trade(trade_data)
    assert trade_id1 > 0
    assert await db.trade_exists("0001193125-24-000099") is True

    # Duplicate insert should return 0 (not last inserted rowid)
    trade_id2 = await db.insert_trade(trade_data)
    assert trade_id2 == 0

@pytest.mark.asyncio
async def test_account_cash_persistence(db):
    # Initially no cash recorded
    cash = await db.get_account_cash("paper")
    assert cash is None

    # Update cash
    await db.update_account_cash("paper", 85000.50)
    cash = await db.get_account_cash("paper")
    assert cash == 85000.50

    # Update again
    await db.update_account_cash("paper", 92000.0)
    cash = await db.get_account_cash("paper")
    assert cash == 92000.0

