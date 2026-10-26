# tests/test_quote_fallback.py
# Yahoo pre-market / illikid durumlarda bid=ask=0 döner; mid lastPrice'tan gelmeli.
from opsi.pricer import enrich
from opsi.scorer import core_score, passes_filters


def test_enrich_falls_back_to_last_price():
    c = {
        "symbol": "F",
        "expiry": "2030-01-01",
        "strike": 13.0,
        "bid": 0.0,
        "ask": 0.0,
        "lastPrice": 0.08,
        "volume": 2417,
        "openInterest": 4323,
    }
    e = enrich(c, S=14.56)
    assert e["mid"] == 0.08
    assert e["quoted"] is False


def test_unquoted_passes_with_liquidity():
    e = {
        "strike": 13.0,
        "dte": 20,
        "delta": -0.2,
        "bid": 0.0,
        "ask": 0.0,
        "mid": 0.08,
        "quoted": False,
        "volume": 2417,
        "openInterest": 4323,
        "iv": 0.3,
    }
    assert passes_filters(e, price=14.56) is True


def test_quoted_path_unchanged():
    c = {
        "symbol": "F",
        "expiry": "2030-01-01",
        "strike": 13.0,
        "bid": 0.07,
        "ask": 0.09,
        "lastPrice": 0.08,
        "volume": 2417,
        "openInterest": 4323,
    }
    e = enrich(c, S=14.56)
    assert e["mid"] == 0.08
    assert e["quoted"] is True


def test_unquoted_liq_not_inflated():
    e = {
        "strike": 13.0,
        "dte": 20,
        "delta": -0.2,
        "bid": 0.0,
        "ask": 0.0,
        "mid": 0.08,
        "quoted": False,
        "volume": 2417,
        "openInterest": 4323,
        "iv": 0.3,
    }
    s = core_score(e, {"iv_min": 0.15, "iv_max": 0.8, "trend": 0.5})
    assert s["liq"] < 1.0
