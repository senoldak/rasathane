import pytest
from inseeder.engine.scorer import compute_conviction_score

def test_ceo_open_market_large_purchase():
    trade = {
        "insider_title": "Chief Executive Officer",
        "is_officer": True,
        "is_director": True,
        "is_ten_percent": False,
        "transaction_code": "P",
        "shares": 20000.0,
        "price": 50.0,
        "value": 1000000.0,
        "shares_owned_after": 40000.0, # 100% increase (had 20000, bought 20000)
        "is_10b5_1": False
    }
    result = compute_conviction_score(trade, cluster_count=2)
    assert result["score"] == 100
    assert result["breakdown"]["role_points"] == 30
    assert result["breakdown"]["value_points"] == 35
    assert result["breakdown"]["increase_points"] == 25
    assert result["breakdown"]["cluster_points"] == 30
    assert result["breakdown"]["discretionary_points"] == 10

def test_cfo_moderate_purchase():
    trade = {
        "insider_title": "Chief Financial Officer",
        "is_officer": True,
        "is_director": False,
        "is_ten_percent": False,
        "transaction_code": "P",
        "shares": 3000.0,
        "price": 50.0,
        "value": 150000.0,
        "shares_owned_after": 13000.0, # was 10000 -> 3000 is 30% increase
        "is_10b5_1": False
    }
    result = compute_conviction_score(trade, cluster_count=1)
    # CFO (+25) + Value $150k (+15) + Increase 30% (+15) + Non-10b5-1 (+10) = 65
    assert result["score"] == 65
    assert result["breakdown"]["role_points"] == 25
    assert result["breakdown"]["value_points"] == 15
    assert result["breakdown"]["increase_points"] == 15

def test_sale_or_award_transaction():
    trade = {
        "insider_title": "CEO",
        "is_officer": True,
        "is_director": False,
        "is_ten_percent": False,
        "transaction_code": "S", # Sale
        "shares": 10000.0,
        "price": 100.0,
        "value": 1000000.0,
        "shares_owned_after": 50000.0,
        "is_10b5_1": True
    }
    result = compute_conviction_score(trade, cluster_count=1)
    # Sales do not get purchase bonuses
    assert result["score"] <= 30

def test_vice_president_role_score():
    trade = {
        "insider_title": "Executive Vice President",
        "is_officer": True,
        "is_director": False,
        "is_ten_percent": False,
        "transaction_code": "P",
        "shares": 1000.0,
        "price": 50.0,
        "value": 50000.0,
        "shares_owned_after": 2000.0,
        "is_10b5_1": False
    }
    result = compute_conviction_score(trade)
    # EVP / VP should receive 15 points (Officer), NOT 20 points (President)
    assert result["breakdown"]["role_points"] == 15

def test_incomplete_or_invalid_shares_owned_after():
    # Case 1: shares_owned_after < shares (data glitch / partial reporting)
    trade_glitch = {
        "insider_title": "Director",
        "is_officer": False,
        "is_director": True,
        "is_ten_percent": False,
        "transaction_code": "P",
        "shares": 5000.0,
        "price": 20.0,
        "value": 100000.0,
        "shares_owned_after": 1000.0, # Less than bought -> cannot calculate increase
        "is_10b5_1": False
    }
    result_glitch = compute_conviction_score(trade_glitch)
    assert result_glitch["breakdown"]["increase_points"] == 0

    # Case 2: shares_owned_after == shares (new position initiation -> +25 pts)
    trade_init = {
        "insider_title": "Director",
        "is_officer": False,
        "is_director": True,
        "is_ten_percent": False,
        "transaction_code": "P",
        "shares": 5000.0,
        "price": 20.0,
        "value": 100000.0,
        "shares_owned_after": 5000.0, # Exact match -> new holding
        "is_10b5_1": False
    }
    result_init = compute_conviction_score(trade_init)
    assert result_init["breakdown"]["increase_points"] == 25

