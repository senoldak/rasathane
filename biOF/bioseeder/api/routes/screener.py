from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bioseeder.database import get_db
from bioseeder.models import CatalystEvent
from bioseeder.api.schemas import ScreenerResponse, ScreenerItemSchema

router = APIRouter()


@router.get("/screener", response_model=ScreenerResponse)
async def screen_catalysts(
    min_score: Optional[float] = Query(None, description="Minimum Bio-Alpha score"),
    min_runway: Optional[float] = Query(None, description="Minimum cash runway in months"),
    max_market_cap: Optional[float] = Query(None, description="Maximum market cap in $M"),
    phase: Optional[str] = Query(None, description="Clinical phase filter"),
    indication: Optional[str] = Query(None, description="Indication or therapeutic area"),
    dilution_risk_only: bool = Query(False, description="Filter only companies with dilution hazard"),
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

        comp = cat.company
        drug = cat.drug
        score = cat.score

        composite = score.composite_score if score else 50.0
        dilution_flag = score.dilution_flag if score else False

        if min_score is not None and composite < min_score:
            continue

        if min_runway is not None and (comp.cash_runway_months is None or comp.cash_runway_months < min_runway):
            continue

        if max_market_cap is not None and (comp.market_cap is None or comp.market_cap > max_market_cap):
            continue

        if phase and phase.lower() not in drug.highest_phase.lower():
            continue

        if indication and (
            indication.lower() not in drug.indication.lower()
            and indication.lower() not in drug.therapeutic_area.lower()
        ):
            continue

        if dilution_risk_only and not dilution_flag:
            continue

        items.append(
            ScreenerItemSchema(
                catalyst_id=cat.id,
                ticker=comp.ticker,
                company_name=comp.name,
                drug_name=drug.code_name or drug.generic_name or "N/A",
                indication=drug.indication,
                phase=drug.highest_phase,
                catalyst_type=cat.catalyst_type,
                target_date=cat.target_date,
                days_to_event=days_to_event,
                market_cap=comp.market_cap,
                cash_runway_months=comp.cash_runway_months,
                composite_score=composite,
                proximity_score=score.proximity_score if score else 50.0,
                pos_score=score.pos_score if score else 50.0,
                asymmetry_score=score.asymmetry_score if score else 50.0,
                dilution_hazard_score=score.dilution_hazard_score if score else 50.0,
                smart_money_score=score.smart_money_score if score else 50.0,
                dilution_flag=dilution_flag,
            )
        )

    # Sort items by composite score descending
    items.sort(key=lambda x: x.composite_score, reverse=True)
    return ScreenerResponse(total=len(items), items=items)
