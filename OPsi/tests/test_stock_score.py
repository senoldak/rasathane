# tests/test_stock_score.py
from opsi.strategies import STRATEGIES


def _snap(**kw):
    d = {
        "close": 20.0,
        "put_volume": 5000,
        "put_oi": 20000,
        "spread_sample": 0.05,
        "stale_flag": 0,
        "earnings_days": 30,
    }
    d.update(kw)
    return d


def test_stock_score_range():
    for name, st in STRATEGIES.items():
        s = st.stock_score(_snap())
        assert 0.0 <= s <= 100.0, name


def test_stale_penalized():
    st = STRATEGIES["csp"]
    assert st.stock_score(_snap()) > st.stock_score(_snap(stale_flag=1))


def test_near_earnings_penalized():
    st = STRATEGIES["csp"]
    assert st.stock_score(_snap()) > st.stock_score(_snap(earnings_days=3))
