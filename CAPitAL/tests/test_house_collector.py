import pytest
import datetime
from sqlalchemy import select
from capitolseeder.db.session import init_db, async_session_maker
from capitolseeder.db.models import Politician, TransactionReport, StockTrade
from capitolseeder.ingestion.house_collector import ingest_house_filing_record

@pytest.mark.asyncio
async def test_ingest_house_filing_record():
    await init_db()
    async with async_session_maker() as session:
        # Ensure politician exists
        pol = await session.get(Politician, "P000197")
        if not pol:
            pol = Politician(
                bioguide_id="P000197",
                first_name="Nancy",
                last_name="Pelosi",
                chamber="House",
                party="Democrat",
                state="CA",
                district=11
            )
            session.add(pol)
            await session.commit()
            
        record = {
            "filing_id": "TEST_H_1009999",
            "bioguide_id": "P000197",
            "filing_date": datetime.date(2024, 7, 2),
            "doc_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2024/1009999.pdf",
            "is_amendment": False,
            "trades": [
                {
                    "ticker": "NVDA",
                    "company_name": "NVIDIA Corporation",
                    "asset_type": "Call_Option",
                    "transaction_type": "Purchase",
                    "transaction_date": datetime.date(2024, 6, 26),
                    "amount_range_str": "$1,000,001 - $5,000,000",
                    "owner_type": "Spouse",
                    "option_strike": 120.0,
                    "option_expiration": datetime.date(2025, 6, 20)
                }
            ]
        }
        
        saved_filing = await ingest_house_filing_record(record, session)
        assert saved_filing is not None
        assert saved_filing.filing_id == "TEST_H_1009999"
        
        # Verify trade was normalized and stored
        res = await session.execute(select(StockTrade).where(StockTrade.filing_id == "TEST_H_1009999"))
        trades = res.scalars().all()
        assert len(trades) == 1
        t = trades[0]
        assert t.ticker == "NVDA"
        assert t.amount_min == 1000001.0
        assert t.filing_lag_days == 6
        assert not t.is_stock_act_violation

        # Test Put Option normalization
        record_put = {
            "filing_id": "TEST_H_PUT_1",
            "bioguide_id": "P000197",
            "filing_date": datetime.date(2024, 7, 10),
            "doc_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2024/put.pdf",
            "is_amendment": False,
            "trades": [
                {
                    "ticker": "SPY",
                    "company_name": "SPDR S&P 500 ETF",
                    "asset_type": "Put Option",
                    "transaction_type": "Purchase",
                    "transaction_date": datetime.date(2024, 7, 5),
                    "amount_range_str": "$15,001 - $50,000",
                    "owner_type": "Self"
                }
            ]
        }
        await ingest_house_filing_record(record_put, session)
        res_put = await session.execute(select(StockTrade).where(StockTrade.filing_id == "TEST_H_PUT_1"))
        put_trade = res_put.scalar_one_or_none()
        assert put_trade is not None
        assert put_trade.asset_type == "Put_Option"
