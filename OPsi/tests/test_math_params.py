# tests/test_math_params.py
"""Ayarlanabilir tarama matematiği: doğrulama, kalıcılık, skor etkisi."""

from fastapi.testclient import TestClient

from opsi import scan
from opsi.academic import apply_academic
from opsi.api import app, get_db_path
from opsi.params import DEFAULT_PARAMS, get_params, norm_weights, normalize_params, save_params
from opsi.scorer import core_score
from opsi.store import init_db


def _ctx():
    return {"iv_min": 0.1, "iv_max": 0.8, "trend": 0.5}


def _leg():
    return {
        "strike": 18.5,
        "dte": 20,
        "delta": -0.2,
        "bid": 0.5,
        "ask": 0.53,
        "mid": 0.515,
        "volume": 200,
        "openInterest": 1000,
        "iv": 0.3,
        "quoted": True,
    }


def test_normalize_bilinmeyeni_atar_araligi_kirpar():
    p = normalize_params(
        {
            "filters": {"dte_min": 60, "dte_max": 10, "spread_max": 99, "bogus": 1},
            "weights": {"ret": 2.0, "otm": -3.0},
            "nope": {"x": 1},
        }
    )
    assert p["filters"]["dte_min"] == 10 and p["filters"]["dte_max"] == 60
    assert p["filters"]["spread_max"] == 0.50
    assert "bogus" not in p["filters"] and "nope" not in p
    assert p["weights"]["ret"] == 1.0 and p["weights"]["otm"] == 0.0
    assert p["flags"] == DEFAULT_PARAMS["flags"]


def test_norm_weights_toplami_bir():
    w = norm_weights({"weights": {"ret": 2.0, "otm": 2.0, "liq": 0, "iv": 0, "trend": 0}})
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["ret"] == w["otm"] == 0.5
    w0 = norm_weights({"weights": {"ret": 0, "otm": 0, "liq": 0, "iv": 0, "trend": 0}})
    assert w0 == {k: DEFAULT_PARAMS["weights"][k] for k in w0}


def test_get_save_roundtrip(tmp_path):
    db = str(tmp_path / "p.db")
    init_db(db)
    assert get_params(db) == DEFAULT_PARAMS
    saved = save_params(db, {"filters": {"dte_min": 7}, "flags": {"jump": False}})
    assert saved["filters"]["dte_min"] == 7 and saved["flags"]["jump"] is False
    assert get_params(db) == saved


def test_core_score_agirlik_etkisi():
    base = core_score(_leg(), _ctx())["score"]
    p = normalize_params({"weights": {"ret": 1.0, "otm": 0, "liq": 0, "iv": 0, "trend": 0}})
    only_ret = core_score(_leg(), _ctx(), params=p)["score"]
    assert only_ret != base
    assert only_ret == 100 * min(1.0, max(0.0, core_score(_leg(), _ctx())["ret_ann"] / 0.6))


def test_academic_ozel_carpan():
    b = core_score(_leg(), _ctx())
    e = {**_leg(), "dte": 30, "iv": 0.9}
    p = normalize_params({"academic": {"m_skew_hi": 0.5}})
    assert apply_academic(b, e, {"skew": True}, params=p)["adj"] == 0.8  # clamp_lo
    assert apply_academic(b, e, {"skew": True}, params=p)["final"] < b["score"]


def test_scan_params_penceresi(tmp_path, monkeypatch):
    import datetime

    db = str(tmp_path / "s.db")
    init_db(db)
    monkeypatch.setattr(scan, "get_price", lambda s: 20.0)
    monkeypatch.setattr(scan, "get_earnings_days", lambda s: None)
    exp = (datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=20)).isoformat()
    chain = [
        {
            "symbol": "AAA",
            "expiry": exp,
            "strike": 18.5,
            "bid": 0.5,
            "ask": 0.53,
            "volume": 200,
            "openInterest": 1000,
        }
    ]
    monkeypatch.setattr(scan, "get_chain", lambda s, right="P": chain)
    sid1 = scan.run_full_scan(db, symbols=["AAA"], strategies=["csp"])
    assert scan.top5(db, sid1)
    # pencere dışı DTE -> aday yok
    sid2 = scan.run_full_scan(
        db,
        symbols=["AAA"],
        strategies=["csp"],
        params=normalize_params({"filters": {"dte_min": 30, "dte_max": 45}}),
    )
    assert scan.top5(db, sid2) == []


def test_api_params_roundtrip(tmp_path):
    db = str(tmp_path / "p.db")
    init_db(db)
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        client = TestClient(app)
        assert client.get("/api/settings/params").json()["active"] == DEFAULT_PARAMS
        resp = client.put("/api/settings/params", json={"params": {"general": {"risk_free": 0.9}}})
        assert resp.status_code == 200
        assert resp.json()["active"]["general"]["risk_free"] == 0.20  # kırpıldı
        assert client.get("/api/settings/params").json()["active"]["general"]["risk_free"] == 0.20
        bad = client.put("/api/settings/params", json={"x": 1})
        assert bad.status_code in (200, 400)
    finally:
        app.dependency_overrides.clear()
