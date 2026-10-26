import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from capitolseeder.db.models import TransactionReport, StockTrade, Politician
from capitolseeder.ingestion.ocr_engine import parse_amount_bracket, calculate_stock_act_lag

def parse_date_flexible(d_val: Any) -> datetime.date:
    if isinstance(d_val, datetime.date):
        return d_val
    if isinstance(d_val, str):
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
            try:
                return datetime.datetime.strptime(d_val.strip(), fmt).date()
            except ValueError:
                continue
    return datetime.date.today()

def normalize_senate_report(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes a raw Senate eFD filing payload into standard schema representation.
    """
    filing_id = raw_payload.get("filing_id", f"DOC_S_{int(datetime.datetime.now().timestamp())}")
    filing_date = parse_date_flexible(raw_payload.get("filing_date"))
    bioguide_id = raw_payload.get("bioguide_id", "")
    
    normalized_trades = []
    for t in raw_payload.get("trades", []):
        tx_date = parse_date_flexible(t.get("transaction_date"))
        disc_date = parse_date_flexible(t.get("disclosure_date", filing_date))
        
        amount_str = t.get("amount_range_str") or t.get("amount") or "$1,001 - $15,000"
        amount_min, amount_max, amount_mid = parse_amount_bracket(amount_str)
        lag_days, is_violation, severity = calculate_stock_act_lag(tx_date, disc_date)
        
        # Normalize owner
        raw_owner = t.get("owner_type") or t.get("owner") or "Self"
        if raw_owner in {"Spouse", "SP"}:
            owner = "Spouse"
        elif raw_owner in {"Joint", "JT"}:
            owner = "Joint"
        elif raw_owner in {"Child", "Dependent Child", "DC"}:
            owner = "Dependent Child"
        else:
            owner = "Self"

        # Normalize asset
        raw_asset = t.get("asset_type") or "Stock"
        raw_asset_lower = raw_asset.lower()
        if "put" in raw_asset_lower:
            asset_type = "Put_Option"
        elif "call" in raw_asset_lower or "option" in raw_asset_lower:
            asset_type = "Call_Option"
        elif "bond" in raw_asset_lower or "treasury" in raw_asset_lower:
            asset_type = "Bond"
        else:
            asset_type = "Stock"

        normalized_trades.append({
            "ticker": (t.get("ticker") or "").upper(),
            "company_name": t.get("company_name") or t.get("asset_description") or f"{t.get('ticker')} Corp",
            "asset_type": asset_type,
            "transaction_type": t.get("transaction_type") or t.get("type") or "Purchase",
            "transaction_date": tx_date,
            "disclosure_date": disc_date,
            "amount_range_str": amount_str,
            "amount_min": amount_min,
            "amount_max": amount_max,
            "amount_midpoint": amount_mid,
            "owner_type": owner,
            "filing_lag_days": lag_days,
            "is_stock_act_violation": is_violation,
            "violation_severity": severity,
            "price_at_transaction": t.get("price_at_transaction"),
            "price_at_disclosure": t.get("price_at_disclosure"),
            "return_30d": t.get("return_30d"),
            "return_90d": t.get("return_90d"),
            "benchmark_return_90d": t.get("benchmark_return_90d")
        })

    return {
        "filing_id": filing_id,
        "bioguide_id": bioguide_id,
        "chamber": "Senate",
        "filing_type": "PTR",
        "filing_date": filing_date,
        "doc_url": raw_payload.get("doc_url", ""),
        "is_amendment": raw_payload.get("is_amendment", False),
        "trades": normalized_trades
    }

async def ingest_senate_report(raw_payload: Dict[str, Any], session: AsyncSession) -> TransactionReport:
    """
    Normalizes and commits a Senate PTR report to the database.
    """
    normalized = normalize_senate_report(raw_payload)
    filing_id = normalized["filing_id"]
    bioguide_id = normalized["bioguide_id"]

    existing_filing = await session.get(TransactionReport, filing_id)
    if not existing_filing:
        filing = TransactionReport(
            filing_id=filing_id,
            bioguide_id=bioguide_id,
            chamber="Senate",
            filing_type="PTR",
            filing_date=normalized["filing_date"],
            doc_url=normalized["doc_url"],
            is_amendment=normalized["is_amendment"]
        )
        session.add(filing)
    else:
        filing = existing_filing

    await session.flush()

    for t in normalized["trades"]:
        stmt = select(StockTrade).where(
            StockTrade.filing_id == filing_id,
            StockTrade.ticker == t["ticker"],
            StockTrade.transaction_date == t["transaction_date"],
            StockTrade.asset_type == t["asset_type"]
        )
        res = await session.execute(stmt)
        if not res.scalar_one_or_none():
            trade = StockTrade(
                filing_id=filing_id,
                bioguide_id=bioguide_id,
                ticker=t["ticker"],
                company_name=t["company_name"],
                asset_type=t["asset_type"],
                transaction_type=t["transaction_type"],
                transaction_date=t["transaction_date"],
                disclosure_date=t["disclosure_date"],
                amount_range_str=t["amount_range_str"],
                amount_min=t["amount_min"],
                amount_max=t["amount_max"],
                amount_midpoint=t["amount_midpoint"],
                owner_type=t["owner_type"],
                filing_lag_days=t["filing_lag_days"],
                is_stock_act_violation=t["is_stock_act_violation"],
                violation_severity=t["violation_severity"],
                price_at_transaction=t.get("price_at_transaction"),
                price_at_disclosure=t.get("price_at_disclosure"),
                return_30d=t.get("return_30d"),
                return_90d=t.get("return_90d"),
                benchmark_return_90d=t.get("benchmark_return_90d")
            )
            session.add(trade)

    await session.commit()
    return filing
