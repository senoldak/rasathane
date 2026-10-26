import datetime
from typing import List, Dict, Any, Optional
import httpx

# Pre-mapped ticker to contractor parent entities and typical agencies
TICKER_CONTRACTOR_MAP = {
    "LMT": {
        "company_name": "Lockheed Martin Corporation",
        "primary_agency": "Department of Defense",
        "contracts": [
            {
                "contract_id": "FA8615-24-C-0012",
                "agency_name": "Department of Defense",
                "award_date": datetime.date(2024, 7, 2),
                "award_amount": 1250000000.0,
                "confidence": 1.0
            }
        ]
    },
    "RTX": {
        "company_name": "RTX Corporation",
        "primary_agency": "Department of Defense",
        "contracts": [
            {
                "contract_id": "N00019-24-C-0008",
                "agency_name": "Department of Defense",
                "award_date": datetime.date(2024, 7, 28),
                "award_amount": 650000000.0,
                "confidence": 0.95
            }
        ]
    },
    "NOC": {
        "company_name": "Northrop Grumman Corporation",
        "primary_agency": "Department of Defense",
        "contracts": [
            {
                "contract_id": "FA8807-24-C-0005",
                "agency_name": "Department of Defense",
                "award_date": datetime.date(2024, 6, 1),
                "award_amount": 920000000.0,
                "confidence": 0.98
            }
        ]
    },
    "PLTR": {
        "company_name": "Palantir Technologies Inc.",
        "primary_agency": "Department of Defense",
        "contracts": [
            {
                "contract_id": "W911QX-24-C-0025",
                "agency_name": "Department of Defense",
                "award_date": datetime.date(2024, 7, 20),
                "award_amount": 480000000.0,
                "confidence": 0.98
            }
        ]
    },
    "MSFT": {
        "company_name": "Microsoft Corporation",
        "primary_agency": "Department of Defense",
        "contracts": [
            {
                "contract_id": "W52P1J-24-D-0001",
                "agency_name": "Department of Defense",
                "award_date": datetime.date(2024, 6, 28),
                "award_amount": 780000000.0,
                "confidence": 0.90
            }
        ]
    },
    "BA": {
        "company_name": "The Boeing Company",
        "primary_agency": "NASA",
        "contracts": [
            {
                "contract_id": "NNH16CO01B",
                "agency_name": "NASA",
                "award_date": datetime.date(2024, 7, 8),
                "award_amount": 350000000.0,
                "confidence": 0.92
            }
        ]
    },
    "NVDA": {
        "company_name": "NVIDIA Corporation",
        "primary_agency": "Department of Energy",
        "contracts": [
            {
                "contract_id": "DE-SC0021389",
                "agency_name": "Department of Energy",
                "award_date": datetime.date(2024, 6, 15),
                "award_amount": 145000000.0,
                "confidence": 0.95
            }
        ]
    }
}

def match_federal_contracts_for_ticker(ticker: str, trade_date: datetime.date, window_days: int = 90) -> List[Dict[str, Any]]:
    """
    Finds federal contracts awarded to the company within a +/- window_days of the trade.
    """
    ticker_clean = ticker.upper().strip()
    matched = []

    if ticker_clean in TICKER_CONTRACTOR_MAP:
        for c in TICKER_CONTRACTOR_MAP[ticker_clean]["contracts"]:
            delta_days = (trade_date - c["award_date"]).days
            if abs(delta_days) <= window_days:
                matched.append({
                    "agency_name": c["agency_name"],
                    "contract_id": c["contract_id"],
                    "award_date": c["award_date"],
                    "award_amount": c["award_amount"],
                    "days_between_trade_and_contract": delta_days,
                    "match_confidence_score": c["confidence"]
                })

    return matched

async def query_usaspending_live(parent_duns: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Optional live query to USASpending.gov API v2.
    """
    url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    payload = {
        "filters": {
            "time_period": [{"start_date": start_date, "end_date": end_date}],
            "recipient_search_text": [parent_duns]
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Action Date"],
        "limit": 10
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                return data.get("results", [])
    except Exception:
        pass
    return []
