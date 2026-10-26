import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from capitolseeder.db.models import TransactionReport, StockTrade, Politician
from capitolseeder.ingestion.ocr_engine import parse_amount_bracket, calculate_stock_act_lag
from capitolseeder.config import get_settings

settings = get_settings()

async def ingest_house_filing_record(record: Dict[str, Any], session: AsyncSession) -> TransactionReport:
    """
    Ingests and normalizes a House PTR filing and its disclosed transactions into the database.
    """
    filing_id = record["filing_id"]
    bioguide_id = record["bioguide_id"]
    
    # Check if filing exists
    existing_filing = await session.get(TransactionReport, filing_id)
    if not existing_filing:
        filing = TransactionReport(
            filing_id=filing_id,
            bioguide_id=bioguide_id,
            chamber="House",
            filing_type=record.get("filing_type", "PTR"),
            filing_date=record.get("filing_date", datetime.date.today()),
            doc_url=record.get("doc_url", ""),
            is_amendment=record.get("is_amendment", False),
            original_filing_id=record.get("original_filing_id"),
            ocr_processed=record.get("ocr_processed", False),
            ocr_raw_text=record.get("ocr_raw_text")
        )
        session.add(filing)
    else:
        filing = existing_filing

    await session.flush()

    for t_data in record.get("trades", []):
        amount_min, amount_max, amount_mid = parse_amount_bracket(t_data.get("amount_range_str", "$1,001 - $15,000"))
        tx_date = t_data.get("transaction_date", filing.filing_date)
        disc_date = t_data.get("disclosure_date", filing.filing_date)
        
        lag_days, is_violation, severity = calculate_stock_act_lag(tx_date, disc_date)

        # Owner type attribution
        owner = t_data.get("owner_type", "Self")
        if owner in {"SP", "Spouse"}:
            owner_norm = "Spouse"
        elif owner in {"JT", "Joint"}:
            owner_norm = "Joint"
        elif owner in {"DC", "Dependent Child"}:
            owner_norm = "Dependent Child"
        else:
            owner_norm = "Self"

        # Asset type normalization
        raw_asset = t_data.get("asset_type", "Stock")
        raw_asset_lower = raw_asset.lower()
        if "put" in raw_asset_lower:
            asset_norm = "Put_Option"
        elif "call" in raw_asset_lower or "option" in raw_asset_lower:
            asset_norm = "Call_Option"
        elif "bond" in raw_asset_lower or "note" in raw_asset_lower:
            asset_norm = "Bond"
        else:
            asset_norm = "Stock"

        # Check existing trade
        stmt = select(StockTrade).where(
            StockTrade.filing_id == filing_id,
            StockTrade.ticker == t_data["ticker"].upper(),
            StockTrade.transaction_date == tx_date,
            StockTrade.asset_type == asset_norm
        )
        res = await session.execute(stmt)
        existing_trade = res.scalar_one_or_none()

        if not existing_trade:
            trade = StockTrade(
                filing_id=filing_id,
                bioguide_id=bioguide_id,
                ticker=t_data["ticker"].upper(),
                company_name=t_data.get("company_name", f"{t_data['ticker']} Inc."),
                asset_type=asset_norm,
                transaction_type=t_data.get("transaction_type", "Purchase"),
                transaction_date=tx_date,
                disclosure_date=disc_date,
                amount_range_str=t_data.get("amount_range_str", "$1,001 - $15,000"),
                amount_min=amount_min,
                amount_max=amount_max,
                amount_midpoint=amount_mid,
                owner_type=owner_norm,
                option_strike=t_data.get("option_strike"),
                option_expiration=t_data.get("option_expiration"),
                filing_lag_days=lag_days,
                is_stock_act_violation=is_violation,
                violation_severity=severity,
                price_at_transaction=t_data.get("price_at_transaction"),
                price_at_disclosure=t_data.get("price_at_disclosure"),
                return_30d=t_data.get("return_30d"),
                return_90d=t_data.get("return_90d"),
                benchmark_return_90d=t_data.get("benchmark_return_90d")
            )
            session.add(trade)
            
    await session.commit()
    return filing
