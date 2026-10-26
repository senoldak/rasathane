import pytest
import datetime
from sqlalchemy import select
from capitolseeder.db.session import init_db, async_session_maker
from capitolseeder.db.models import Politician, StockTrade, TransactionReport
from capitolseeder.ingestion.senate_collector import normalize_senate_report, ingest_senate_report

def test_normalize_senate_report():
    raw_payload = {
        "senator_name": "Tommy Tuberville",
        "bioguide_id": "T000278",
        "filing_id": "DOC_2024_S_982103",
        "filing_date": "08/15/2024",
        "doc_url": "https://efdsearch.senate.gov/search/view/ptr/982103/",
        "trades": [
            {
                "transaction_date": "07/10/2024",
                "ticker": "LMT",
                "company_name": "Lockheed Martin Corporation",
                "asset_type": "Stock",
                "transaction_type": "Purchase",
                "amount_range_str": "$100,001 - $250,000",
                "owner_type": "Self"
            }
        ]
    }
    normalized = normalize_senate_report(raw_payload)
    assert len(normalized["trades"]) == 1
    trade = normalized["trades"][0]
    assert trade["ticker"] == "LMT"
    assert trade["amount_min"] == 100001.0
    assert trade["amount_max"] == 250000.0
    assert trade["filing_lag_days"] == 36
    assert not trade["is_stock_act_violation"]

@pytest.mark.asyncio
async def test_ingest_senate_report():
    await init_db()
    async with async_session_maker() as session:
        # Ensure Tuberville exists
        pol = await session.get(Politician, "T000278")
        if not pol:
            pol = Politician(
                bioguide_id="T000278",
                first_name="Tommy",
                last_name="Tuberville",
                chamber="Senate",
                party="Republican",
                state="AL"
            )
            session.add(pol)
            await session.commit()

        raw_payload = {
            "senator_name": "Tommy Tuberville",
            "bioguide_id": "T000278",
            "filing_id": "DOC_2024_S_TEST_99",
            "filing_date": "08/15/2024",
            "doc_url": "https://efdsearch.senate.gov/search/view/ptr/TEST99/",
            "trades": [
                {
                    "transaction_date": "07/10/2024",
                    "ticker": "LMT",
                    "company_name": "Lockheed Martin Corporation",
                    "asset_type": "Stock",
                    "transaction_type": "Purchase",
                    "amount_range_str": "$100,001 - $250,000",
                    "owner_type": "Self"
                }
            ]
        }
        filing = await ingest_senate_report(raw_payload, session)
        assert filing.filing_id == "DOC_2024_S_TEST_99"
        
        stmt = select(StockTrade).where(StockTrade.filing_id == "DOC_2024_S_TEST_99")
        res = await session.execute(stmt)
        trades = res.scalars().all()
        assert len(trades) == 1
        assert trades[0].ticker == "LMT"

def test_senate_put_option_normalization():
    raw_payload = {
        "senator_name": "Test Senator",
        "bioguide_id": "T000278",
        "filing_id": "DOC_2024_S_PUT_TEST",
        "filing_date": "08/15/2024",
        "doc_url": "https://efdsearch.senate.gov/search/view/ptr/PUT/",
        "trades": [
            {
                "transaction_date": "07/10/2024",
                "ticker": "SPY",
                "company_name": "SPDR S&P 500 ETF Trust",
                "asset_type": "Put Option",
                "transaction_type": "Purchase",
                "amount_range_str": "$100,001 - $250,000",
                "owner_type": "Self"
            }
        ]
    }
    normalized = normalize_senate_report(raw_payload)
    assert normalized["trades"][0]["asset_type"] == "Put_Option"
