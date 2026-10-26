import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from bioseeder.collectors.clinicaltrials import ClinicalTrialsCollector
from bioseeder.collectors.openfda import OpenFDACollector
from bioseeder.collectors.market_data import MarketDataCollector
from bioseeder.collectors.base import BaseCollector


@pytest.mark.asyncio
async def test_parse_clinical_trials_study_v2_official_schema():
    collector = ClinicalTrialsCollector()
    # Official ClinicalTrials.gov API v2 schema: enrollmentInfo is directly under designModule
    mock_payload = {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT04208555",
                        "briefTitle": "A Study of VX-548 in Acute Pain",
                    },
                    "statusModule": {
                        "overallStatus": "COMPLETED",
                        "primaryCompletionDateStruct": {
                            "date": "2024-03-15",
                            "type": "ACTUAL",
                        },
                    },
                    "designModule": {
                        "phases": ["PHASE3"],
                        "studyType": "INTERVENTIONAL",
                        "enrollmentInfo": {"count": 1118},
                    },
                    "descriptionModule": {
                        "briefSummary": "A randomized, double-blind Phase 3 study evaluating VX-548."
                    },
                    "armsInterventionsModule": {
                        "interventions": [
                            {"name": "VX-548", "type": "DRUG"}
                        ]
                    },
                }
            }
        ]
    }
    parsed = collector.parse_studies(mock_payload)
    assert len(parsed) == 1
    study = parsed[0]
    assert study["nct_id"] == "NCT04208555"
    assert study["title"] == "A Study of VX-548 in Acute Pain"
    assert study["phase"] == "Phase 3"
    assert study["status"] == "Completed"
    assert study["primary_completion_date"] == date(2024, 3, 15)
    assert study["enrollment"] == 1118
    assert "VX-548" in study["interventions"]


@pytest.mark.asyncio
async def test_parse_clinical_trials_study_nested_fallback():
    collector = ClinicalTrialsCollector()
    # Fallback schema: enrollmentInfo nested inside designInfo
    mock_payload = {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT09999999",
                        "briefTitle": "A Fallback Schema Study",
                    },
                    "statusModule": {
                        "overallStatus": "RECRUITING",
                        "primaryCompletionDateStruct": {
                            "date": "2026-06-30",
                            "type": "ESTIMATED",
                        },
                    },
                    "designModule": {
                        "phases": ["PHASE2"],
                        "studyType": "INTERVENTIONAL",
                        "designInfo": {"enrollmentInfo": {"count": 450}},
                    },
                    "descriptionModule": {
                        "briefSummary": "Phase 2 testing fallback extraction."
                    },
                    "armsInterventionsModule": {
                        "interventions": [{"name": "MOCK-101", "type": "DRUG"}]
                    },
                }
            }
        ]
    }
    parsed = collector.parse_studies(mock_payload)
    assert len(parsed) == 1
    study = parsed[0]
    assert study["nct_id"] == "NCT09999999"
    assert study["enrollment"] == 450
    assert study["phase"] == "Phase 2"


@pytest.mark.asyncio
async def test_parse_openfda_drug_approvals():
    collector = OpenFDACollector()
    mock_payload = {
        "results": [
            {
                "application_number": "NDA218000",
                "sponsor_name": "Vertex Pharmaceuticals Inc",
                "products": [
                    {
                        "brand_name": "JOURNAVO",
                        "active_ingredients": [{"name": "SUZETRIGINE"}],
                        "dosage_form": "TABLET",
                    }
                ],
                "submissions": [
                    {
                        "submission_type": "ORIG",
                        "submission_number": "1",
                        "submission_status": "AP",
                        "submission_status_date": "20250130",
                    }
                ],
            }
        ]
    }
    parsed = collector.parse_approvals(mock_payload)
    assert len(parsed) == 1
    appr = parsed[0]
    assert appr["application_number"] == "NDA218000"
    assert appr["sponsor_name"] == "Vertex Pharmaceuticals Inc"
    assert appr["brand_name"] == "JOURNAVO"
    assert appr["active_ingredient"] == "SUZETRIGINE"
    assert appr["status"] == "AP"
    assert appr["approval_date"] == date(2025, 1, 30)


@pytest.mark.asyncio
async def test_parse_openfda_multiple_submissions_sorts_descending():
    collector = OpenFDACollector()
    # Provide multiple submissions out of chronological order.
    # The collector must sort by submission_status_date descending to pick the latest decision (AP on 2025-02-15).
    mock_payload = {
        "results": [
            {
                "application_number": "NDA123456",
                "sponsor_name": "BioPharma Corp",
                "products": [{"brand_name": "TESTDRUG", "active_ingredients": [{"name": "TEST"}], "dosage_form": "VIAL"}],
                "submissions": [
                    {
                        "submission_type": "ORIG",
                        "submission_number": "1",
                        "submission_status": "CR",
                        "submission_status_date": "20230501",
                    },
                    {
                        "submission_type": "SUPPL",
                        "submission_number": "2",
                        "submission_status": "AP",
                        "submission_status_date": "20250215",
                    },
                    {
                        "submission_type": "SUPPL",
                        "submission_number": "1",
                        "submission_status": "TA",
                        "submission_status_date": "20240110",
                    },
                ],
            }
        ]
    }
    parsed = collector.parse_approvals(mock_payload)
    assert len(parsed) == 1
    appr = parsed[0]
    assert appr["status"] == "AP"
    assert appr["approval_date"] == date(2025, 2, 15)


def test_market_data_runway_calculation():
    collector = MarketDataCollector()
    # 1000M cash / (200M burn per quarter / 3) = 15 months runway
    runway = collector.calculate_cash_runway(cash_m=1000.0, quarterly_burn_m=200.0)
    assert runway == 15.0

    # Negative or zero burn (profitable / cash generating) -> 999.0 months
    runway_profitable = collector.calculate_cash_runway(cash_m=500.0, quarterly_burn_m=-50.0)
    assert runway_profitable == 999.0


@pytest.mark.asyncio
async def test_base_collector_404_raises_immediately_without_retries():
    collector = BaseCollector(base_url="https://api.example.com", max_retries=3)
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", "https://api.example.com/endpoint")
        return httpx.Response(404, request=req, json={"error": "Not found"})

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await collector.get("endpoint")
        assert exc_info.value.response.status_code == 404
        # Must NOT have retried 3 times; should fail on attempt 0 (call_count == 1)
        assert call_count == 1


@pytest.mark.asyncio
async def test_base_collector_500_retries_and_raises():
    collector = BaseCollector(base_url="https://api.example.com", max_retries=2)
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", "https://api.example.com/endpoint")
        return httpx.Response(500, request=req, json={"error": "Server error"})

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await collector.get("endpoint")
            assert exc_info.value.response.status_code == 500
            # Attempt 0, attempt 1, attempt 2 -> 3 total calls
            assert call_count == 3

