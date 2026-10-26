from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from capitolseeder.db.session import get_db
from capitolseeder.db.models import Politician, StockTrade, CommitteeMembership
from capitolseeder.api.schemas import PoliticianLeaderboardItem, PoliticianDetailResponse, StockTradeResponse

router = APIRouter(prefix="/politicians", tags=["Politicians"])

@router.get("/leaderboard", response_model=List[PoliticianLeaderboardItem])
async def get_leaderboard(
    chamber: Optional[str] = Query(None),
    party: Optional[str] = Query(None),
    sort_by: str = Query("alpha"),  # 'alpha', 'win_rate', 'volume'
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    trade_count_subq = (
        select(StockTrade.bioguide_id, func.count(StockTrade.id).label("trade_count"))
        .group_by(StockTrade.bioguide_id)
        .subquery()
    )
    query = (
        select(Politician, func.coalesce(trade_count_subq.c.trade_count, 0).label("trade_count"))
        .outerjoin(trade_count_subq, Politician.bioguide_id == trade_count_subq.c.bioguide_id)
    )

    if chamber:
        query = query.where(Politician.chamber.ilike(f"%{chamber}%"))
    if party:
        query = query.where(Politician.party.ilike(f"%{party}%"))

    if sort_by == "win_rate":
        query = query.order_by(desc(Politician.win_rate))
    elif sort_by == "volume":
        query = query.order_by(desc(Politician.total_volume))
    else:
        query = query.order_by(desc(Politician.alpha_score))

    query = query.limit(limit)
    res = await db.execute(query)
    rows = res.all()

    items = []
    for p, trade_count in rows:
        items.append(PoliticianLeaderboardItem(
            bioguide_id=p.bioguide_id,
            first_name=p.first_name,
            last_name=p.last_name,
            chamber=p.chamber,
            party=p.party,
            state=p.state,
            district=p.district,
            leadership_title=p.leadership_title,
            image_url=p.image_url,
            win_rate=p.win_rate,
            total_volume=p.total_volume,
            alpha_score=p.alpha_score,
            total_trades_count=trade_count
        ))
    return items

@router.get("/{bioguide_id}", response_model=PoliticianDetailResponse)
async def get_politician_dossier(
    bioguide_id: str,
    db: AsyncSession = Depends(get_db)
):
    pol = await db.get(Politician, bioguide_id)
    if not pol:
        raise HTTPException(status_code=404, detail="Politician not found")

    # Total trades count from DB
    total_trades_stmt = select(func.count(StockTrade.id)).where(StockTrade.bioguide_id == bioguide_id)
    total_trades_res = await db.execute(total_trades_stmt)
    total_trades_count = total_trades_res.scalar() or 0

    # Load committees
    comm_res = await db.execute(
        select(CommitteeMembership).where(CommitteeMembership.bioguide_id == bioguide_id)
    )
    committees = comm_res.scalars().all()

    # Load recent trades with contracts & alpha scores
    trades_res = await db.execute(
        select(StockTrade)
        .where(StockTrade.bioguide_id == bioguide_id)
        .options(
            selectinload(StockTrade.alpha_score),
            selectinload(StockTrade.contract_matches)
        )
        .order_by(desc(StockTrade.disclosure_date))
        .limit(20)
    )
    recent_trades = trades_res.scalars().all()

    # Calculate actual economic sector breakdown
    TICKER_SECTORS = {
        "NVDA": "Technology / Semiconductors",
        "MSFT": "Technology / Software",
        "AAPL": "Technology / Consumer Electronics",
        "LMT": "Defense & Aerospace",
        "RTX": "Defense & Aerospace",
        "NOC": "Defense & Aerospace",
        "BA": "Aerospace & Aviation",
        "PLTR": "Defense & Enterprise AI",
        "CVX": "Energy / Oil & Gas",
        "XOM": "Energy / Oil & Gas",
        "AVGO": "Technology / Semiconductors",
        "SPY": "Broad Market ETF"
    }
    sector_counts = {}
    for t in recent_trades:
        sec = TICKER_SECTORS.get(t.ticker.upper(), "Equities / Other")
        sector_counts[sec] = sector_counts.get(sec, 0) + 1

    trades_schemas = []
    for t in recent_trades:
        trades_schemas.append(StockTradeResponse(
            id=t.id,
            filing_id=t.filing_id,
            bioguide_id=t.bioguide_id,
            politician_name=f"{pol.first_name} {pol.last_name}",
            party=pol.party,
            state=pol.state,
            chamber=pol.chamber,
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
        ))

    return PoliticianDetailResponse(
        politician=PoliticianLeaderboardItem(
            bioguide_id=pol.bioguide_id,
            first_name=pol.first_name,
            last_name=pol.last_name,
            chamber=pol.chamber,
            party=pol.party,
            state=pol.state,
            district=pol.district,
            leadership_title=pol.leadership_title,
            image_url=pol.image_url,
            win_rate=pol.win_rate,
            total_volume=pol.total_volume,
            alpha_score=pol.alpha_score,
            total_trades_count=total_trades_count
        ),
        committees=[
            {
                "committee_code": c.committee_code,
                "committee_name": c.committee_name,
                "subcommittee_name": c.subcommittee_name,
                "role": c.role,
                "jurisdiction_keywords": c.jurisdiction_keywords if isinstance(c.jurisdiction_keywords, list) else []
            }
            for c in committees
        ],
        recent_trades=trades_schemas,
        sector_breakdown=sector_counts,
        win_rate_vs_spy=pol.win_rate
    )
