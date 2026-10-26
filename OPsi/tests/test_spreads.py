# tests/test_spreads.py
from opsi.strategies import STRATEGIES
from opsi.strategies.bull_put_spread import BullPutSpread
from opsi.strategies.iron_condor import IronCondor


def _leg(**kw):
    d = {
        "symbol": "AAA",
        "expiry": "2026-10-16",
        "strike": 18.5,
        "bid": 0.5,
        "ask": 0.53,
        "lastPrice": 0.5,
        "volume": 200,
        "openInterest": 1000,
        "mid": 0.5,
        "dte": 20,
        "quoted": True,
        "iv": 0.3,
        "delta": -0.2,
    }
    d.update(kw)
    return d


def _puts():
    return [
        _leg(strike=18.5, delta=-0.2, bid=0.48, ask=0.52, mid=0.5),
        _leg(strike=17.0, delta=-0.1, bid=0.19, ask=0.21, mid=0.2),
        _leg(strike=16.0, delta=-0.05, bid=0.09, ask=0.11, mid=0.1),
        _leg(strike=10.0, delta=-0.01, bid=0.04, ask=0.06, mid=0.05),
    ]


def _calls(price=19.0):
    return [
        _leg(strike=21.0, delta=0.2, bid=0.39, ask=0.41, mid=0.4),
        _leg(strike=22.5, delta=0.1, bid=0.19, ask=0.21, mid=0.2),
    ]


def test_registry_has_four():
    assert set(STRATEGIES) == {"csp", "covered_call", "bull_put_spread", "iron_condor"}


def test_bull_put_spread_positions_and_math():
    bps = BullPutSpread()
    assert bps.universe_ok(19.0) is True
    # Spread teminatı makasla sınırlı olduğundan pahalı hisse elenmez; sadece fiyatsız elenir
    assert bps.universe_ok(30.0) is True
    assert bps.universe_ok(315.0) is True
    assert bps.universe_ok(None) is False
    pos = bps.positions(_puts(), 19.0)
    assert pos, "eşleşme bekleniyordu"
    p0 = pos[0]
    assert p0["strategy"] == "bull_put_spread"
    assert len(p0["legs"]) == 2
    width = p0["legs"][0]["strike"] - p0["legs"][1]["strike"]
    assert 0 < width <= 5.0
    assert p0["premium"] > 0
    assert p0["capital"] == width * 100 - p0["premium"] * 100
    s = bps.score(p0, {})
    assert 0 <= s["score"] <= 100


def test_bull_put_spread_rejects_debit():
    bps = BullPutSpread()
    legs = [
        _leg(strike=18.5, delta=-0.2, mid=0.1),
        _leg(strike=17.0, delta=-0.1, mid=0.5),  # long pahalı → net debit
    ]
    assert bps.positions(legs, 19.0) == []


def test_iron_condor_builds_four_legs():
    ic = IronCondor()
    assert ic.rights == ("P", "C")
    pos = ic.positions(_puts() + _calls(), 19.0)
    assert pos, "condor eşleşmesi bekleniyordu"
    p0 = pos[0]
    assert len(p0["legs"]) == 4
    assert p0["premium"] > 0
    assert p0["capital"] > 0
    s = ic.score(p0, {})
    assert 0 <= s["score"] <= 100


def test_iron_condor_rejects_crossed():
    ic = IronCondor()
    # put-long (20) call-short (19.5) üstünde → bacaklar kesişiyor, elenmeli
    puts = [_leg(strike=21.0, delta=-0.2, mid=0.5), _leg(strike=20.0, delta=-0.1, mid=0.2)]
    calls = [_leg(strike=19.5, delta=0.2, mid=0.4), _leg(strike=21.0, delta=0.1, mid=0.2)]
    assert ic.positions(puts + calls, 19.0) == []
