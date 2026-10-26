from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bioseeder.database import get_db
from bioseeder.models import Company, DrugCandidate, ClinicalTrial, CatalystEvent
from bioseeder.api.schemas import (
    CompanyDossierResponse,
    DrugCandidateSchema,
    ClinicalTrialSchema,
    CatalystItemSchema,
    ScoreBreakdownSchema,
)

router = APIRouter()


@router.get("/companies")
async def list_companies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).order_by(Company.ticker.asc()))
    companies = result.scalars().all()
    return [
        {
            "id": c.id,
            "ticker": c.ticker,
            "name": c.name,
            "exchange": c.exchange,
            "market_cap": c.market_cap,
            "cash_runway_months": c.cash_runway_months,
        }
        for c in companies
    ]


@router.get("/company/{ticker}", response_model=CompanyDossierResponse)
async def get_company_dossier(ticker: str, db: AsyncSession = Depends(get_db)):
    query = (
        select(Company)
        .where(Company.ticker == ticker.upper())
        .options(
            selectinload(Company.drugs).selectinload(DrugCandidate.trials),
            selectinload(Company.catalysts).selectinload(CatalystEvent.drug),
            selectinload(Company.catalysts).selectinload(CatalystEvent.score),
        )
    )

    result = await db.execute(query)
    comp = result.scalar_one_or_none()

    if not comp:
        raise HTTPException(status_code=404, detail=f"Company with ticker '{ticker}' not found")

    today = date.today()

    drugs_schema = []
    for d in comp.drugs:
        trials_schema = [
            ClinicalTrialSchema(
                nct_id=t.nct_id,
                title=t.title,
                phase=t.phase,
                status=t.status,
                primary_completion_date=t.primary_completion_date,
                enrollment=t.enrollment,
            )
            for t in d.trials
        ]
        drugs_schema.append(
            DrugCandidateSchema(
                id=d.id,
                code_name=d.code_name,
                generic_name=d.generic_name,
                brand_name=d.brand_name,
                indication=d.indication,
                therapeutic_area=d.therapeutic_area,
                highest_phase=d.highest_phase,
                target_tam=d.target_tam,
                mechanism_of_action=d.mechanism_of_action,
                trials=trials_schema,
            )
        )

    catalysts_schema = []
    for cat in comp.catalysts:
        days_to_event = (cat.target_date - today).days
        score = cat.score
        breakdown = ScoreBreakdownSchema(
            proximity_score=score.proximity_score if score else 50.0,
            pos_score=score.pos_score if score else 50.0,
            asymmetry_score=score.asymmetry_score if score else 50.0,
            dilution_hazard_score=score.dilution_hazard_score if score else 50.0,
            smart_money_score=score.smart_money_score if score else 50.0,
        )
        catalysts_schema.append(
            CatalystItemSchema(
                id=cat.id,
                ticker=comp.ticker,
                company_name=comp.name,
                exchange=comp.exchange,
                market_cap=comp.market_cap,
                cash_runway_months=comp.cash_runway_months,
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
                bio_alpha_score=score.composite_score if score else 50.0,
                dilution_flag=score.dilution_flag if score else False,
                score_breakdown=breakdown,
            )
        )

    return CompanyDossierResponse(
        ticker=comp.ticker,
        name=comp.name,
        exchange=comp.exchange,
        market_cap=comp.market_cap,
        enterprise_value=comp.enterprise_value,
        cash_and_equivalents=comp.cash_and_equivalents,
        quarterly_burn_rate=comp.quarterly_burn_rate,
        cash_runway_months=comp.cash_runway_months,
        float_shares=comp.float_shares,
        short_interest_pct=comp.short_interest_pct,
        drugs=drugs_schema,
        catalysts=catalysts_schema,
    )
