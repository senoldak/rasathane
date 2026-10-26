from opsi.scorer import core_score


def test_percentile_rank():
    e = _e(iv=0.5)
    ctx = {"iv_min": 0.1, "iv_max": 0.8, "iv_history": [0.2, 0.3, 0.4, 0.5] * 5}
    s = core_score(e, ctx)
    assert (
        abs(s["iv_rank"] - 1.0) < 1e-9
    )  # 20 değerin 20'si <= 0.5 (brief'teki 0.8 miscount; formül verbatim)


def test_fallback_short_history():
    e = _e(iv=0.5)
    s = core_score(e, {"iv_min": 0.1, "iv_max": 0.8, "iv_history": [0.2]})
    assert abs(s["iv_rank"] - (0.5 - 0.1) / 0.7) < 1e-9


def _e(**kw):
    d = {
        "strike": 18.0,
        "dte": 20,
        "delta": -0.2,
        "bid": 0.5,
        "ask": 0.53,
        "mid": 0.515,
        "quoted": True,
        "volume": 200,
        "openInterest": 1000,
        "iv": 0.3,
    }
    d.update(kw)
    return d
