# tests/test_academic_branches.py
from opsi.academic import apply_academic, kelly_fraction


def _base(score=70.0):
    return {
        "score": score,
        "ret_ann": 0.3,
        "prob_otm": 0.8,
        "liq": 0.7,
        "iv_rank": 0.6,
        "trend": 0.5,
    }


def test_skew_high_penalizes():
    out = apply_academic(_base(), {"iv": 0.7, "dte": 20}, {"skew": True})
    assert out["final"] < 70.0
    assert any("kuyruk" in n for n in out["notes"])


def test_skew_mid_rewards():
    out = apply_academic(_base(), {"iv": 0.5, "dte": 20}, {"skew": True})
    assert out["final"] > 70.0


def test_term_short_penalizes():
    out = apply_academic(_base(), {"iv": 0.3, "dte": 15}, {"term": True})
    assert out["final"] < 70.0


def test_jump_near_earnings_penalizes():
    out = apply_academic(_base(), {"iv": 0.3, "dte": 20, "earnings_days": 5}, {"jump": True})
    assert out["final"] < 70.0


def test_flags_off_no_change():
    out = apply_academic(_base(), {"iv": 0.9, "dte": 10, "earnings_days": 1}, {})
    assert out["final"] == 70.0
    assert out["notes"] == []


def test_kelly_edges():
    assert kelly_fraction(0.1, 0.0) == 0.0
    assert kelly_fraction(0.1, -1.0) == 0.0
    assert kelly_fraction(1.0, 0.5) == 0.25  # cap
    assert kelly_fraction(0.05, 1.0) == 0.05
