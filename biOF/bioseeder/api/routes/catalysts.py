from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bioseeder.database import get_db
from bioseeder.models import CatalystEvent, Company, DrugCandidate, BioAlphaScore
from bioseeder.api.schemas import CatalystListResponse, CatalystItemSchema, ScoreBreakdownSchema

router = APIRouter()


def _build_catalyst_item(cat: CatalystEvent, today: date) -> CatalystItemSchema:
    days_to_event = (cat.target_date - today).days
    score = cat.score
    composite = score.composite_score if score else 50.0
    dilution_flag = score.dilution_flag if score else False

    breakdown = ScoreBreakdownSchema(
        proximity_score=score.proximity_score if score else 50.0,
        pos_score=score.pos_score if score else 50.0,
        asymmetry_score=score.asymmetry_score if score else 50.0,
        dilution_hazard_score=score.dilution_hazard_score if score else 50.0,
        smart_money_score=score.smart_money_score if score else 50.0,
    )

    return CatalystItemSchema(
        id=cat.id,
        ticker=cat.company.ticker,
        company_name=cat.company.name,
        exchange=cat.company.exchange,
        market_cap=cat.company.market_cap,
        cash_runway_months=cat.company.cash_runway_months,
        drug_name=cat.drug.code_name or cat.drug.generic_name or "N/A",
        generic_name=cat.drug.generic_name,
        indication=cat.drug.indication,
        therapeutic_area=cat.drug.therapeutic_area,
        phase=cat.drug.highest_phase,
        catalyst_type=cat.catalyst_type,
        target_date=cat.target_date,
        days_to_event=days_to_event,
        date_precision=cat.date_precision,
        status=cat.status,
        outcome=cat.outcome,
        details=cat.details,
        bio_alpha_score=composite,
        dilution_flag=dilution_flag,
        score_breakdown=breakdown,
    )


@router.get("/catalysts", response_model=CatalystListResponse)
async def get_catalysts(
    days_ahead: Optional[int] = Query(None, description="Max days ahead to filter"),
    phase: Optional[str] = Query(None, description="Clinical phase filter"),
    indication: Optional[str] = Query(None, description="Indication or therapeutic area filter"),
    min_score: Optional[float] = Query(None, description="Minimum Bio-Alpha score"),
    catalyst_type: Optional[str] = Query(None, description="Catalyst type filter"),
    include_past: bool = Query(False, description="Include completed or past events"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(CatalystEvent)
        .join(CatalystEvent.company)
        .join(CatalystEvent.drug)
        .outerjoin(CatalystEvent.score)
        .options(
            selectinload(CatalystEvent.company),
            selectinload(CatalystEvent.drug),
            selectinload(CatalystEvent.score),
        )
        .order_by(CatalystEvent.target_date.asc())
    )

    result = await db.execute(query)
    catalysts = result.scalars().all()
    today = date.today()

    items = []
    for cat in catalysts:
        days_to_event = (cat.target_date - today).days

        if not include_past and days_to_event < 0:
            continue

        if days_ahead is not None and (days_to_event > days_ahead or days_to_event < 0):
            continue

        if phase and phase.lower() not in cat.drug.highest_phase.lower():
            continue

        if indication and (
            indication.lower() not in cat.drug.indication.lower()
            and indication.lower() not in cat.drug.therapeutic_area.lower()
        ):
            continue

        if catalyst_type and catalyst_type.lower() not in cat.catalyst_type.lower():
            continue

        score_val = cat.score.composite_score if cat.score else 50.0
        if min_score is not None and score_val < min_score:
            continue

        items.append(_build_catalyst_item(cat, today))

    return CatalystListResponse(total=len(items), items=items)


@router.get("/pdufa-calendar", response_model=CatalystListResponse)
async def get_pdufa_calendar(
    days_ahead: Optional[int] = Query(None, description="Max days ahead"),
    include_past: bool = Query(False, description="Include completed or past events"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(CatalystEvent)
        .join(CatalystEvent.company)
        .join(CatalystEvent.drug)
        .outerjoin(CatalystEvent.score)
        .where(CatalystEvent.catalyst_type.in_(["PDUFA", "FDA Approval", "AdCom Meeting"]))
        .options(
            selectinload(CatalystEvent.company),
            selectinload(CatalystEvent.drug),
            selectinload(CatalystEvent.score),
        )
        .order_by(CatalystEvent.target_date.asc())
    )

    result = await db.execute(query)
    catalysts = result.scalars().all()
    today = date.today()

    items = []
    for cat in catalysts:
        days_to_event = (cat.target_date - today).days
        if not include_past and days_to_event < 0:
            continue
        if days_ahead is not None and (days_to_event > days_ahead or days_to_event < 0):
            continue
        items.append(_build_catalyst_item(cat, today))

    return CatalystListResponse(total=len(items), items=items)
