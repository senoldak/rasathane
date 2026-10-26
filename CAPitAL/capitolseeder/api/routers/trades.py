from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import selectinload
from capitolseeder.db.session import get_db
from capitolseeder.db.models import StockTrade, Politician, CapitolAlphaScore, FederalContractMatch
from capitolseeder.api.schemas import PaginatedTradesResponse, StockTradeResponse
from capitolseeder.ingestion.live_feed import sync_live_congress_trades

router = APIRouter(prefix="/trades", tags=["Trades"])

@router.post("/sync")
async def sync_trades_now(limit: int = Query(100, ge=1, le=500)):
    """
    Manually trigger real-time synchronization from live congressional stream.
    """
    new_count = await sync_live_congress_trades(limit=limit)
    return {
        "status": "success",
        "new_trades_count": new_count,
        "message": f"Successfully processed stream. Ingested {new_count} new disclosure(s)."
    }


@router.get("", response_model=PaginatedTradesResponse)
async def list_trades(
    party: Optional[str] = Query(None),
    chamber: Optional[str] = Query(None),
    committee: Optional[str] = Query(None),
    ticker: Optional[str] = Query(None),
    owner_type: Optional[str] = Query(None),
    is_violation: Optional[bool] = Query(None),
    min_score: Optional[float] = Query(None),
    sort_by: str = Query("disclosure_date"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(StockTrade).join(StockTrade.politician).outerjoin(StockTrade.alpha_score).options(
        selectinload(StockTrade.politician),
        selectinload(StockTrade.alpha_score),
        selectinload(StockTrade.contract_matches)
    )

    if party:
        query = query.where(Politician.party.ilike(f"%{party}%"))
    if chamber:
        query = query.where(Politician.chamber.ilike(f"%{chamber}%"))
    if ticker:
        query = query.where(StockTrade.ticker == ticker.upper().strip())
    if owner_type:
        query = query.where(StockTrade.owner_type.ilike(f"%{owner_type}%"))
    if is_violation is not None:
        query = query.where(StockTrade.is_stock_act_violation == is_violation)
    if min_score is not None:
        query = query.where(CapitolAlphaScore.composite_alpha_score >= min_score)
    if committee:
        from capitolseeder.db.models import CommitteeMembership
        query = query.join(Politician.committees).where(
            (CommitteeMembership.committee_name.ilike(f"%{committee}%")) |
            (CommitteeMembership.committee_code.ilike(f"%{committee}%"))
        )

    # Sort
    if sort_by == "transaction_date":
        sort_col = StockTrade.transaction_date
    elif sort_by == "amount":
        sort_col = StockTrade.amount_midpoint
    elif sort_by == "alpha":
        sort_col = CapitolAlphaScore.composite_alpha_score
    else:
        sort_col = StockTrade.disclosure_date

    query = query.order_by(desc(sort_col) if order == "desc" else asc(sort_col))

    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(query)
    trades = res.scalars().all()

    items = []
    for t in trades:
        item = StockTradeResponse(
            id=t.id,
            filing_id=t.filing_id,
            bioguide_id=t.bioguide_id,
            politician_name=f"{t.politician.first_name} {t.politician.last_name}" if t.politician else None,
            party=t.politician.party if t.politician else None,
            state=t.politician.state if t.politician else None,
            chamber=t.politician.chamber if t.politician else None,
            ticker=t.ticker,
            company_name=t.company_name,
            asset_type=t.asset_type,
            transaction_type=t.transaction_type,
            transaction_date=t.transaction_date,
            disclosure_date=t.disclosure_date,
            amount_range_str=t.amount_range_str,
            amount_min=t.amount_min,
            amount_max=t.amount_max,
            amount_midpoint=t.amount_midpoint,
            owner_type=t.owner_type,
            option_strike=t.option_strike,
            option_expiration=t.option_expiration,
            filing_lag_days=t.filing_lag_days,
            is_stock_act_violation=t.is_stock_act_violation,
            violation_severity=t.violation_severity,
            price_at_transaction=t.price_at_transaction,
            price_at_disclosure=t.price_at_disclosure,
            return_30d=t.return_30d,
            return_90d=t.return_90d,
            benchmark_return_90d=t.benchmark_return_90d,
            alpha_score=t.alpha_score,
            contracts=[
                {
                    "agency_name": c.agency_name,
                    "contract_id": c.contract_id,
                    "award_date": c.award_date,
                    "award_amount": c.award_amount,
                    "days_between_trade_and_contract": c.days_between_trade_and_contract,
                    "match_confidence_score": c.match_confidence_score
                }
                for c in t.contract_matches
            ]
        )
        items.append(item)

    return PaginatedTradesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )
