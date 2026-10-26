import pytest
import datetime
from capitolseeder.ingestion.contract_matcher import match_federal_contracts_for_ticker

def test_contract_matching():
    # LMT matches DoD contracts
    matches = match_federal_contracts_for_ticker("LMT", datetime.date(2024, 7, 10))
    assert len(matches) > 0
    assert matches[0]["agency_name"] == "Department of Defense"
    assert matches[0]["award_amount"] > 0
    assert abs(matches[0]["days_between_trade_and_contract"]) <= 90

    # PLTR matches DoD / Intelligence contracts
    pltr_matches = match_federal_contracts_for_ticker("PLTR", datetime.date(2024, 7, 25))
    assert len(pltr_matches) > 0
    assert "Defense" in pltr_matches[0]["agency_name"] or "DoD" in pltr_matches[0]["agency_name"]
