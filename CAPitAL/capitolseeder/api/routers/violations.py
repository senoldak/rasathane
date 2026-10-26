from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from capitolseeder.db.session import get_db
from capitolseeder.db.models import StockTrade, Politician, TransactionReport
from capitolseeder.api.schemas import ViolationsResponse, ViolationItem
from capitolseeder.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/violations", tags=["STOCK Act Violations"])

@router.get("", response_model=ViolationsResponse)
async def list_violations(
    severity: Optional[str] = Query(None),  # 'Moderate', 'Severe'
    party: Optional[str] = Query(None),
    chamber: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(StockTrade)
        .join(StockTrade.politician)
        .join(StockTrade.filing)
        .options(
            selectinload(StockTrade.politician),
            selectinload(StockTrade.filing)
        )
        .where(StockTrade.is_stock_act_violation == True)
    )

    if severity:
        query = query.where(StockTrade.violation_severity.ilike(f"%{severity}%"))
    if party:
        query = query.where(Politician.party.ilike(f"%{party}%"))
    if chamber:
        query = query.where(Politician.chamber.ilike(f"%{chamber}%"))

    # Count and estimate fines for all matching violations in DB
    all_lags_query = (
        select(StockTrade.filing_lag_days)
        .join(StockTrade.politician)
        .where(StockTrade.is_stock_act_violation == True)
    )
    if severity:
        all_lags_query = all_lags_query.where(StockTrade.violation_severity.ilike(f"%{severity}%"))
    if party:
        all_lags_query = all_lags_query.where(Politician.party.ilike(f"%{party}%"))
    if chamber:
        all_lags_query = all_lags_query.where(Politician.chamber.ilike(f"%{chamber}%"))

    all_lags_res = await db.execute(all_lags_query)
    all_lags = all_lags_res.scalars().all()
    total_db_count = len(all_lags)
    total_db_fines = 0.0
    for lag in all_lags:
        days_over = max(0, lag - settings.stock_act_grace_days)
        f = settings.statutory_fine_base
        if days_over > 30:
            f += ((days_over - 30) // 30) * 100.0
        total_db_fines += f

    query = query.order_by(desc(StockTrade.filing_lag_days)).limit(limit)
    res = await db.execute(query)
    viol_trades = res.scalars().all()

    items = []
    for t in viol_trades:
        days_over = max(0, t.filing_lag_days - settings.stock_act_grace_days)
        # Statutory fine estimation: $200 base + $100 per 30 days overdue
        est_fine = settings.statutory_fine_base
        if days_over > 30:
            est_fine += ((days_over - 30) // 30) * 100.0

        items.append(ViolationItem(
            trade_id=t.id,
            filing_id=t.filing_id,
            bioguide_id=t.bioguide_id,
            politician_name=f"{t.politician.first_name} {t.politician.last_name}" if t.politician else "Unknown",
            party=t.politician.party if t.politician else "",
            chamber=t.politician.chamber if t.politician else "",
            ticker=t.ticker,
            transaction_date=t.transaction_date,
            disclosure_date=t.disclosure_date,
            filing_lag_days=t.filing_lag_days,
            days_overdue=days_over,
            violation_severity=t.violation_severity,
            estimated_statutory_fine=est_fine,
            doc_url=t.filing.doc_url if t.filing else ""
        ))

    return ViolationsResponse(
        total_violations_count=total_db_count,
        total_estimated_fines=total_db_fines,
        violations=items
    )
