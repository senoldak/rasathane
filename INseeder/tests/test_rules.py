import pytest
from inseeder.engine.rules import evaluate_rules

def test_evaluate_rules_matching():
    trade = {
        "ticker": "NVDA",
        "insider_title": "CEO",
        "is_officer": True,
        "is_director": True,
        "is_ten_percent": False,
        "transaction_code": "P",
        "value": 250000.0,
    }
    score = 80
    rules = [
        {
            "id": 1,
            "name": "High Conviction Exec Buys",
            "is_active": 1,
            "min_score": 70,
            "min_value": 100000.0,
            "allowed_roles": '["CEO", "CFO"]',
            "allowed_types": '["P"]',
            "auto_execute": 1,
            "broker_target": "paper",
            "position_size_usd": 5000.0
        },
        {
            "id": 2,
            "name": "Mega Buys",
            "is_active": 1,
            "min_score": 90, # Score is 80, should NOT match
            "min_value": 1000000.0,
            "allowed_roles": '["CEO"]',
            "allowed_types": '["P"]',
            "auto_execute": 0,
            "broker_target": "paper",
            "position_size_usd": 10000.0
        }
    ]

    matched = evaluate_rules(trade, score, rules)
    assert len(matched) == 1
    assert matched[0]["id"] == 1
    assert matched[0]["name"] == "High Conviction Exec Buys"

def test_evaluate_rules_inactive_ignored():
    trade = {"insider_title": "CEO", "transaction_code": "P", "value": 500000.0}
    rules = [{"id": 1, "is_active": 0, "min_score": 50, "min_value": 10000.0, "allowed_roles": '["CEO"]', "allowed_types": '["P"]'}]
    matched = evaluate_rules(trade, 80, rules)
    assert len(matched) == 0

def test_evaluate_rules_case_insensitive_and_expanded_roles():
    # Trade by COO with lowercase 'p' in rule
    trade_coo = {
        "ticker": "AAPL",
        "insider_title": "Chief Operating Officer",
        "is_officer": True,
        "is_director": False,
        "is_ten_percent": False,
        "transaction_code": "P",
        "value": 200000.0,
    }
    rules = [
        {
            "id": 10,
            "name": "COO Lowercase P Rule",
            "is_active": 1,
            "min_score": 60,
            "min_value": 50000.0,
            "allowed_roles": '["COO"]',
            "allowed_types": '["p"]', # lowercase p
            "auto_execute": 0,
            "broker_target": "paper",
            "position_size_usd": 5000.0
        },
        {
            "id": 11,
            "name": "President Rule",
            "is_active": 1,
            "min_score": 60,
            "min_value": 50000.0,
            "allowed_roles": '["President"]',
            "allowed_types": '["P"]',
            "auto_execute": 0,
            "broker_target": "paper",
            "position_size_usd": 5000.0
        }
    ]
    matched = evaluate_rules(trade_coo, 75, rules)
    assert len(matched) == 1
    assert matched[0]["id"] == 10

