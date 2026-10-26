from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from capitolseeder.db.session import get_db
from capitolseeder.db.models import StockTrade, Politician, CapitolAlphaScore, FederalContractMatch, CommitteeMembership
from capitolseeder.api.schemas import ConflictTradeResponse, StockTradeResponse

router = APIRouter(prefix="/conflicts", tags=["Conflicts"])

@router.get("/live", response_model=List[ConflictTradeResponse])
async def get_live_conflicts(
    min_conflict_score: float = Query(75.0, ge=0.0, le=100.0),
    has_contract: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(StockTrade)
        .join(StockTrade.alpha_score)
        .join(StockTrade.politician)
        .options(
            selectinload(StockTrade.politician).selectinload(Politician.committees),
            selectinload(StockTrade.alpha_score),
            selectinload(StockTrade.contract_matches)
        )
        .where(CapitolAlphaScore.conflict_score >= min_conflict_score)
    )

    if has_contract is True:
        stmt = stmt.where(StockTrade.contract_matches.any())
    elif has_contract is False:
        stmt = stmt.where(~StockTrade.contract_matches.any())

    stmt = stmt.order_by(desc(CapitolAlphaScore.conflict_score)).limit(limit)

    res = await db.execute(stmt)
    trades = res.scalars().all()

    from capitolseeder.engine.scoring_engine import TICKER_KEYWORD_MAP

    conflicts = []
    for t in trades:
        comm_name = "Congressional Committee"
        comm_role = "Member"
        if t.politician and t.politician.committees:
            t_keywords = set(TICKER_KEYWORD_MAP.get(t.ticker.upper(), []))
            best_comm = None
            max_overlap = -1
            for cm in t.politician.committees:
                cm_kws = {k.lower() for k in cm.jurisdiction_keywords} if isinstance(cm.jurisdiction_keywords, list) else set()
                overlap_len = len(t_keywords.intersection(cm_kws))
                if overlap_len > max_overlap:
                    max_overlap = overlap_len
                    best_comm = cm
            
            target_comm = best_comm or t.politician.committees[0]
            comm_name = target_comm.committee_name
            comm_role = target_comm.role

        rationale = ""
        if t.alpha_score and isinstance(t.alpha_score.rationale, dict):
            rationale = t.alpha_score.rationale.get("conflict", "")

        conflicts.append(ConflictTradeResponse(
            trade=StockTradeResponse(
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
            ),
            committee_name=comm_name,
            committee_role=comm_role,
            conflict_score=t.alpha_score.conflict_score if t.alpha_score else 0.0,
            rationale=rationale,
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

    return conflicts
