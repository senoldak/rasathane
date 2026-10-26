from opsi.academic import apply_academic


def test_academic_bounded():
    base = {
        "score": 70.0,
        "ret_ann": 0.3,
        "prob_otm": 0.8,
        "liq": 0.7,
        "iv_rank": 0.6,
        "trend": 0.5,
    }
    e = {"iv": 0.5, "dte": 20, "delta": -0.2, "strike": 18.0}
    out = apply_academic(base, e, {"skew": True, "term": True, "jump": True})
    assert 56.0 <= out["final"] <= 84.0
