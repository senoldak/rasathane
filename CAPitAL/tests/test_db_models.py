import pytest
import datetime
from sqlalchemy import select
from capitolseeder.db.session import init_db, async_session_maker
from capitolseeder.db.models import Politician, CommitteeMembership, StockTrade, TransactionReport, CapitolAlphaScore

@pytest.mark.asyncio
async def test_database_init_and_crud():
    await init_db()
    async with async_session_maker() as session:
        # Check if already exists or create isolated test politician
        existing = await session.get(Politician, "TEST_P000197")
        if not existing:
            politician = Politician(
                bioguide_id="TEST_P000197",
                first_name="Nancy",
                last_name="Pelosi",
                chamber="House",
                party="Democrat",
                state="CA",
                district=11,
                leadership_title="Speaker Emerita",
                win_rate=68.5,
                total_volume=45000000.0,
                alpha_score=84.2
            )
            session.add(politician)
            
            # Create committee
            cm = CommitteeMembership(
                bioguide_id="TEST_P000197",
                committee_code="HSCF",
                committee_name="House Democratic Leadership",
                role="Member",
                jurisdiction_keywords=["technology", "semiconductors", "appropriations"]
            )
            session.add(cm)
            
            # Create filing
            filing = TransactionReport(
                filing_id="DOC_TEST_1002934",
                bioguide_id="TEST_P000197",
                chamber="House",
                filing_date=datetime.date(2024, 7, 2),
                doc_url="https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2024/1002934.pdf",
                is_amendment=False
            )
            session.add(filing)
            
            # Create trade
            trade = StockTrade(
                filing_id="DOC_TEST_1002934",
                bioguide_id="TEST_P000197",
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                asset_type="Call_Option",
                transaction_type="Purchase",
                transaction_date=datetime.date(2024, 6, 26),
                disclosure_date=datetime.date(2024, 7, 2),
                amount_range_str="$1,000,001 - $5,000,000",
                amount_min=1000001.0,
                amount_max=5000000.0,
                amount_midpoint=3000000.5,
                owner_type="Spouse",
                filing_lag_days=6,
                is_stock_act_violation=False,
                violation_severity="None"
            )
            session.add(trade)
            await session.commit()
            
        # Query back
        res = await session.execute(select(Politician).where(Politician.bioguide_id == "TEST_P000197"))
        pol = res.scalar_one_or_none()
        assert pol is not None
        assert pol.last_name == "Pelosi"
        
        # Query trade
        t_res = await session.execute(select(StockTrade).where(StockTrade.filing_id == "DOC_TEST_1002934"))
        saved_trade = t_res.scalar_one_or_none()
        assert saved_trade is not None
        assert saved_trade.owner_type == "Spouse"
        assert saved_trade.amount_min == 1000001.0
