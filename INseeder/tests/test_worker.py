import pytest
import pytest_asyncio
import os
from unittest.mock import AsyncMock, patch
from inseeder.db.database import Database
from inseeder.execution.paper_broker import PaperBroker
from inseeder.execution.notifier import Notifier
from inseeder.worker import IngestionWorker

@pytest_asyncio.fixture
async def setup_worker():
    test_db_path = "test_worker.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    db = Database(db_path=test_db_path)
    await db.init_db()

    # Insert an active auto-execute rule
    await db.insert_rule({
        "name": "Auto Exec CEO Buys",
        "is_active": 1,
        "min_score": 70,
        "min_value": 50000.0,
        "allowed_roles": '["CEO"]',
        "allowed_types": '["P"]',
        "auto_execute": 1,
        "broker_target": "paper",
        "position_size_usd": 5000.0
    })

    broker = PaperBroker(db=db, initial_cash=100000.0)
    notifier = Notifier()
    worker = IngestionWorker(db=db, broker=broker, notifier=notifier)

    yield worker, db, broker

    await db.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

@pytest.mark.asyncio
async def test_worker_pipeline_run_once(setup_worker):
    worker, db, broker = setup_worker

    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_form4.xml")
    with open(fixture_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    # Mock collector feed and XML fetch
    fake_entries = [{
        "accession_no": "0001234567-26-000001",
        "index_url": "https://sec.gov/Archives/sample-index.htm",
        "title": "4 - XYZ CORP",
        "updated": "2026-09-20"
    }]

    with patch.object(worker.collector, "fetch_feed", new_callable=AsyncMock) as mock_feed, \
         patch.object(worker.collector, "fetch_form4_xml", new_callable=AsyncMock) as mock_xml, \
         patch.object(worker.notifier, "send_signal_alert", new_callable=AsyncMock) as mock_notify:

        mock_feed.return_value = fake_entries
        mock_xml.return_value = xml_content
        mock_notify.return_value = True

        processed_count = await worker.run_once()
        assert processed_count == 1

        # Verify trade was inserted
        trades = await db.get_trades(limit=10)
        assert len(trades) == 1
        assert trades[0]["ticker"] == "XYZ"

        # Verify signal was generated (CEO buy with $500k value scores 90+)
        signals = await db.get_signals()
        assert len(signals) == 1
        assert signals[0]["score"] >= 70

        # Verify paper order was auto-executed
        orders = await db.get_orders()
        assert len(orders) == 1
        assert orders[0]["symbol"] == "XYZ"
        assert orders[0]["status"] == "filled"

        # Verify notification was sent
        assert mock_notify.called

@pytest.mark.asyncio
async def test_worker_deduplication_across_cycles(setup_worker):
    worker, db, broker = setup_worker

    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_form4.xml")
    with open(fixture_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    fake_entries = [{
        "accession_no": "0001234567-26-000099",
        "index_url": "https://sec.gov/Archives/sample-index.htm",
        "title": "4 - XYZ CORP",
        "updated": "2026-09-20"
    }]

    with patch.object(worker.collector, "fetch_feed", new_callable=AsyncMock) as mock_feed, \
         patch.object(worker.collector, "fetch_form4_xml", new_callable=AsyncMock) as mock_xml, \
         patch.object(worker.notifier, "send_signal_alert", new_callable=AsyncMock) as mock_notify:

        mock_feed.return_value = fake_entries
        mock_xml.return_value = xml_content
        mock_notify.return_value = True

        # First cycle: should process 1
        count1 = await worker.run_once()
        assert count1 == 1
        assert mock_xml.call_count == 1

        # Second cycle with same accession number: should be skipped before fetch_form4_xml
        mock_xml.reset_mock()
        count2 = await worker.run_once()
        assert count2 == 0
        assert mock_xml.call_count == 0  # XML download skipped completely!

