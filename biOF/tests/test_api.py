import pytest
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from bioseeder.api.main import app
from bioseeder.config import get_settings
from bioseeder.models import Company, DrugCandidate, CatalystEvent, BioAlphaScore


@pytest.mark.asyncio
async def test_api_endpoints_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        health_res = await client.get("/api/v1/health")
        assert health_res.status_code == 200
        health_json = health_res.json()
        assert health_json["status"] == "healthy"
        assert health_json["database"] == "connected"

        # 2. Seed data
        seed_res = await client.post("/api/v1/seed")
        assert seed_res.status_code == 200
        seed_data = seed_res.json()
        assert seed_data["companies_seeded"] > 0
        assert seed_data["catalysts_seeded"] > 0

        # 3. Catalysts list (defaults to include_past=False)
        cat_res = await client.get("/api/v1/catalysts")
        assert cat_res.status_code == 200
        cat_data = cat_res.json()
        assert len(cat_data["items"]) > 0
        first_item = cat_data["items"][0]
        assert "ticker" in first_item
        assert "bio_alpha_score" in first_item
        # Verify no past events returned by default
        assert all(item["days_to_event"] >= 0 for item in cat_data["items"])

        # 4. PDUFA calendar
        pdufa_res = await client.get("/api/v1/pdufa-calendar")
        assert pdufa_res.status_code == 200
        pdufa_data = pdufa_res.json()
        assert len(pdufa_data["items"]) > 0
        assert all(item["catalyst_type"] in ("PDUFA", "FDA Approval", "AdCom Meeting") for item in pdufa_data["items"])

        # 5. Screener endpoint
        screener_res = await client.get("/api/v1/screener", params={"min_score": 50.0})
        assert screener_res.status_code == 200
        screener_data = screener_res.json()
        assert all(item["composite_score"] >= 50.0 for item in screener_data["items"])

        # 6. Company dossier
        dossier_res = await client.get("/api/v1/company/VRTX")
        assert dossier_res.status_code == 200
        dossier_data = dossier_res.json()
        assert dossier_data["ticker"] == "VRTX"
        assert len(dossier_data["drugs"]) > 0

        # 7. Live approvals feed
        feed_res = await client.get("/api/v1/approvals/live")
        assert feed_res.status_code == 200
        feed_data = feed_res.json()
        assert "feed" in feed_data


@pytest.mark.asyncio
async def test_catalyst_temporal_filtering(db_session):
    today = date.today()
    company = Company(ticker="TEMP", name="Temporal Bio", exchange="NASDAQ", market_cap=500.0)
    db_session.add(company)
    await db_session.flush()

    drug = DrugCandidate(company_id=company.id, code_name="TMP-01", indication="Test", therapeutic_area="Oncology", highest_phase="Phase 2")
    db_session.add(drug)
    await db_session.flush()

    cat_past = CatalystEvent(
        company_id=company.id, drug_id=drug.id, catalyst_type="Data Readout",
        target_date=today - timedelta(days=20), status="COMPLETED", outcome="POSITIVE"
    )
    cat_near_future = CatalystEvent(
        company_id=company.id, drug_id=drug.id, catalyst_type="Phase 2 Data",
        target_date=today + timedelta(days=15), status="UPCOMING", outcome="PENDING"
    )
    cat_far_future = CatalystEvent(
        company_id=company.id, drug_id=drug.id, catalyst_type="PDUFA",
        target_date=today + timedelta(days=60), status="UPCOMING", outcome="PENDING"
    )
    db_session.add_all([cat_past, cat_near_future, cat_far_future])
    await db_session.flush()

    for cat in [cat_past, cat_near_future, cat_far_future]:
        score = BioAlphaScore(
            catalyst_id=cat.id, composite_score=75.0, proximity_score=75.0,
            pos_score=50.0, asymmetry_score=50.0, dilution_hazard_score=50.0,
            smart_money_score=50.0, dilution_flag=False
        )
        db_session.add(score)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default: exclude past events
        res = await client.get("/api/v1/catalysts")
        assert res.status_code == 200
        items = res.json()["items"]
        assert all(i["days_to_event"] >= 0 for i in items)
        types = [i["catalyst_type"] for i in items]
        assert "Data Readout" not in types
        assert "Phase 2 Data" in types
        assert "PDUFA" in types

        # include_past=True: past events should be present
        res_past = await client.get("/api/v1/catalysts?include_past=true")
        assert res_past.status_code == 200
        items_past = res_past.json()["items"]
        types_past = [i["catalyst_type"] for i in items_past]
        assert "Data Readout" in types_past

        # days_ahead=30: should include near future (15d) but exclude far future (60d) and past (-20d)
        res_30 = await client.get("/api/v1/catalysts?days_ahead=30")
        assert res_30.status_code == 200
        items_30 = res_30.json()["items"]
        types_30 = [i["catalyst_type"] for i in items_30]
        assert "Phase 2 Data" in types_30
        assert "PDUFA" not in types_30
        assert "Data Readout" not in types_30


@pytest.mark.asyncio
async def test_screener_excludes_null_market_cap(db_session):
    today = date.today()
    comp_null_cap = Company(ticker="NOCAP", name="No Cap Bio", exchange="NASDAQ", market_cap=None)
    comp_valid_cap = Company(ticker="WITHCAP", name="With Cap Bio", exchange="NASDAQ", market_cap=300.0)
    db_session.add_all([comp_null_cap, comp_valid_cap])
    await db_session.flush()

    drug1 = DrugCandidate(company_id=comp_null_cap.id, code_name="DRUG-1", indication="Test", therapeutic_area="Oncology", highest_phase="Phase 2")
    drug2 = DrugCandidate(company_id=comp_valid_cap.id, code_name="DRUG-2", indication="Test", therapeutic_area="Oncology", highest_phase="Phase 2")
    db_session.add_all([drug1, drug2])
    await db_session.flush()

    cat1 = CatalystEvent(company_id=comp_null_cap.id, drug_id=drug1.id, catalyst_type="Phase 2", target_date=today + timedelta(days=10), status="UPCOMING", outcome="PENDING")
    cat2 = CatalystEvent(company_id=comp_valid_cap.id, drug_id=drug2.id, catalyst_type="Phase 2", target_date=today + timedelta(days=10), status="UPCOMING", outcome="PENDING")
    db_session.add_all([cat1, cat2])
    await db_session.flush()

    for c in [cat1, cat2]:
        s = BioAlphaScore(catalyst_id=c.id, composite_score=80.0, proximity_score=80.0, pos_score=50.0, asymmetry_score=50.0, dilution_hazard_score=50.0, smart_money_score=50.0, dilution_flag=False)
        db_session.add(s)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Filter with max_market_cap=500.0
        # NOCAP has market_cap=None, so it must be excluded!
        res = await client.get("/api/v1/screener", params={"max_market_cap": 500.0})
        assert res.status_code == 200
        items = res.json()["items"]
        tickers = [i["ticker"] for i in items]
        assert "WITHCAP" in tickers
        assert "NOCAP" not in tickers


@pytest.mark.asyncio
async def test_seed_authentication_in_production_mode():
    settings = get_settings()
    original_debug = settings.DEBUG
    original_key = settings.ADMIN_API_KEY
    try:
        settings.DEBUG = False
        settings.ADMIN_API_KEY = "test-secret-key-123"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Unauthenticated request without header -> 403 Forbidden
            unauth_res = await client.post("/api/v1/seed")
            assert unauth_res.status_code == 403
            assert "Database seeding is restricted" in unauth_res.json()["detail"]

            # 2. Request with invalid key -> 403 Forbidden
            bad_key_res = await client.post("/api/v1/seed", headers={"X-Admin-Key": "wrong-key"})
            assert bad_key_res.status_code == 403

            # 3. Request with valid key -> 200 OK
            auth_res = await client.post("/api/v1/seed", headers={"X-Admin-Key": "test-secret-key-123"})
            assert auth_res.status_code == 200
            assert auth_res.json()["companies_seeded"] > 0
    finally:
        settings.DEBUG = original_debug
        settings.ADMIN_API_KEY = original_key

