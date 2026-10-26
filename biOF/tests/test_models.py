import pytest
from datetime import date, datetime, timezone
from sqlalchemy import select
from bioseeder.models import Company, DrugCandidate, ClinicalTrial, CatalystEvent, BioAlphaScore


@pytest.mark.asyncio
async def test_create_and_query_company_and_pipeline(db_session):
    session = db_session
    if True:
        company = Company(
            ticker="VRTX",
            name="Vertex Pharmaceuticals",
            exchange="NASDAQ",
            market_cap=115000.0,
            cash_and_equivalents=10500.0,
            quarterly_burn_rate=650.0,
            cash_runway_months=48.5,
        )
        session.add(company)
        await session.flush()

        drug = DrugCandidate(
            company_id=company.id,
            code_name="VX-548",
            generic_name="Suzetrigine",
            brand_name="Journavo",
            indication="Moderate-to-Severe Acute Pain",
            therapeutic_area="Pain / Neurology",
            target_tam=4500.0,
            highest_phase="NDA/BLA",
            mechanism_of_action="Selective NaV1.8 inhibitor",
        )
        session.add(drug)
        await session.flush()

        trial = ClinicalTrial(
            nct_id="NCT04208555",
            drug_id=drug.id,
            title="A Study of VX-548 in Acute Pain",
            phase="Phase 3",
            status="Completed",
            primary_completion_date=date(2024, 3, 15),
            study_type="Interventional",
            enrollment=1118,
            brief_summary="Phase 3 study assessing efficacy and safety of VX-548 for acute pain.",
        )
        session.add(trial)
        await session.flush()

        catalyst = CatalystEvent(
            company_id=company.id,
            drug_id=drug.id,
            trial_id=trial.id,
            catalyst_type="PDUFA",
            target_date=date(2026, 1, 30),
            date_precision="EXACT",
            status="UPCOMING",
            outcome="PENDING",
            details="FDA PDUFA target action date for Suzetrigine (VX-548) in acute pain.",
        )
        session.add(catalyst)
        await session.flush()

        score = BioAlphaScore(
            catalyst_id=catalyst.id,
            composite_score=84.5,
            proximity_score=78.0,
            pos_score=88.0,
            asymmetry_score=65.0,
            dilution_hazard_score=95.0,
            smart_money_score=70.0,
            dilution_flag=False,
            calculated_at=datetime.now(timezone.utc),
        )
        session.add(score)
        await session.commit()

        # Query back and verify relationships
        res = await session.execute(
            select(Company).where(Company.ticker == "VRTX")
        )
        fetched_comp = res.scalar_one()
        assert fetched_comp.name == "Vertex Pharmaceuticals"
        assert len(fetched_comp.drugs) == 1

        fetched_drug = fetched_comp.drugs[0]
        assert fetched_drug.code_name == "VX-548"
        assert len(fetched_drug.catalysts) == 1
        assert len(fetched_drug.trials) == 1

        fetched_catalyst = fetched_drug.catalysts[0]
        assert fetched_catalyst.catalyst_type == "PDUFA"
        assert fetched_catalyst.score is not None
        assert fetched_catalyst.score.composite_score == 84.5
        assert fetched_catalyst.score.dilution_flag is False
