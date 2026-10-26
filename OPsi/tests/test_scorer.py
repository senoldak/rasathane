# tests/test_scorer.py
from opsi.scorer import core_score, passes_filters


def test_csp_capital_filter():
    e = {
        "strike": 25.0,
        "dte": 20,
        "delta": -0.2,
        "bid": 0.5,
        "ask": 0.53,
        "volume": 200,
        "openInterest": 1000,
        "iv": 0.3,
    }
    assert passes_filters(e, price=24.0) is False


def test_core_score_range():
    e = {
        "strike": 18.0,
        "dte": 20,
        "delta": -0.2,
        "bid": 0.5,
        "ask": 0.53,
        "volume": 200,
        "openInterest": 1000,
        "iv": 0.3,
        "mid": 0.515,
    }
    s = core_score(e, {"iv_min": 0.2, "iv_max": 0.6, "trend": 0.6})
    assert 0 <= s["score"] <= 100


def test_core_score_ret_ann():
    e = {
        "strike": 20.0,
        "dte": 30,
        "delta": -0.2,
        "bid": 0.48,
        "ask": 0.52,
        "volume": 200,
        "openInterest": 1000,
        "iv": 0.3,
        "mid": 0.50,
    }
    # capital = 20 * 100 = 2000 USD
    # premium = 0.50 * 100 = 50 USD
    # 30-day return = 50 / 2000 = 0.025 (2.5%)
    # annualized = 0.025 * (365 / 30) = ~0.30416 (30.4%)
    s = core_score(e, {"iv_min": 0.2, "iv_max": 0.6, "trend": 0.6})
    expected = (0.50 * 100 / 2000.0) * (365.0 / 30)
    assert abs(s["ret_ann"] - expected) < 1e-6
    assert 0.25 <= s["ret_ann"] <= 0.35
