# tests/test_universes.py
"""Hazır endeks evrenleri: registry bütünlüğü, önbellek zinciri, migration.

Tümü çevrimdışı çalışır; ağ fonksiyonları monkeypatch ile patlatılır.
Sahte fiyat/zincir YOKTUR — fallback'lar gerçek sembol listeleridir.
"""

import json
import sqlite3

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from opsi import fetch
from opsi.api import app
from opsi.config import UNIVERSES
from opsi.scan import load_universe
from opsi.store import init_db


def _boom(*a, **k):
    raise ConnectionError("ağ kapalı (test)")


def test_registry_bultenlugu():
    assert {"sp500", "nasdaq100", "dow30", "russell2000_liquid", "sectors", "bist30"} <= set(
        UNIVERSES
    )
    for uid, meta in UNIVERSES.items():
        assert meta.get("title") and meta.get("desc"), uid
        assert meta.get("kind") in ("static", "url"), uid
        if meta["kind"] == "static":
            syms = meta["symbols"]
            assert len(syms) >= 10, uid
            assert all(s == s.strip() and s for s in syms), uid
    bist = UNIVERSES["bist30"]["symbols"]
    assert all(s.endswith(".IS") for s in bist)
    assert len({s for s in UNIVERSES["dow30"]["symbols"]}) == 30
    assert len({s for s in UNIVERSES["nasdaq100"]["symbols"]}) >= 80
    assert len({s for s in UNIVERSES["russell2000_liquid"]["symbols"]}) >= 50


def test_static_evren_agsiz_cozulur(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "read_csv", _boom)
    syms = fetch.get_universe_symbols("dow30", cache_dir=str(tmp_path))
    assert syms == sorted({s for s in UNIVERSES["dow30"]["symbols"]})
    # önbellek dosyası yazıldı
    cached = json.loads((tmp_path / "dow30.json").read_text(encoding="utf-8"))
    assert len(cached["symbols"]) == 30 and cached["fetched_at"]


def test_url_evren_taze_onbellekle_ag_kullanmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "read_csv", _boom)
    fresh = {"symbols": ["AAA", "BBB"], "fetched_at": "2099-01-01T00:00:00+00:00"}
    (tmp_path / "sp500.json").write_text(json.dumps(fresh), encoding="utf-8")
    assert fetch.get_universe_symbols("sp500", cache_dir=str(tmp_path)) == ["AAA", "BBB"]


def test_url_evren_bayat_onbellege_duser(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "read_csv", _boom)
    stale = {"symbols": ["ZZZ"], "fetched_at": "2000-01-01T00:00:00+00:00"}
    (tmp_path / "sp500.json").write_text(json.dumps(stale), encoding="utf-8")
    assert fetch.get_universe_symbols("sp500", cache_dir=str(tmp_path)) == ["ZZZ"]


def test_bilinmeyen_evren_hata():
    with pytest.raises(KeyError):
        fetch.get_universe_symbols("hayalet")


def test_universe_info_agsiz(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "read_csv", _boom)
    info = fetch.universe_info("bist30", cache_dir=str(tmp_path))
    assert info["currency"] == "TRY"
    assert info["count"] == len({s for s in UNIVERSES["bist30"]["symbols"]})


def test_fx_hatada_none_sahte_kur_yok(tmp_path, monkeypatch):
    import yfinance as yf

    monkeypatch.setattr(yf.Ticker, "history", _boom)
    assert fetch.get_fx_to_usd("TRY", cache_dir=str(tmp_path)) is None
    assert fetch.get_fx_to_usd("XXX", cache_dir=str(tmp_path)) is None
    assert fetch.get_fx_to_usd("USD") == 1.0
    # kur yoksa ham fiyat aynen döner
    assert fetch.price_in_usd("THYAO.IS", 100.0, cache_dir=str(tmp_path)) == 100.0
    assert fetch.price_in_usd("AAPL", 100.0, cache_dir=str(tmp_path)) == 100.0
    assert fetch.price_in_usd("AAPL", None) is None


def test_load_universe_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "read_csv", _boom)
    out = load_universe(str(tmp_path / "u.db"), universe="sectors")
    assert out == sorted({s for s in UNIVERSES["sectors"]["symbols"]})


def test_scans_universe_kolonu(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    with sqlite3.connect(db) as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(scans)").fetchall()]
        assert "universe" in cols
        con.execute(
            "INSERT INTO scans(started_at, status, universe) VALUES(?,?,?)", ("t", "done", "dow30")
        )
        assert con.execute("SELECT universe FROM scans").fetchone()[0] == "dow30"


def test_api_universes():
    client = TestClient(app)
    resp = client.get("/api/universes")
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()["universes"]}
    assert {"sp500", "nasdaq100", "dow30", "russell2000_liquid", "sectors", "bist30"} <= ids


def test_api_scans_universe_etiketli(tmp_path):
    from opsi.api import get_db_path

    db = str(tmp_path / "t.db")
    init_db(db)
    with sqlite3.connect(db) as con:
        con.execute(
            "INSERT INTO scans(started_at, status, universe, n_candidates) VALUES(?,?,?,?)",
            ("2026-09-09T00:00:00", "done", "dow30", 12),
        )
        con.commit()
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        resp = TestClient(app).get("/api/scans?limit=5")
        assert resp.status_code == 200
        scans = resp.json()["scans"]
        assert len(scans) == 1
        assert scans[0]["universe"] == "dow30"
        assert scans[0]["n_candidates"] == 12
    finally:
        app.dependency_overrides.clear()


def test_scan_custom_bilinmeyen_evren_400(tmp_path):
    from opsi.api import get_db_path

    db = str(tmp_path / "t.db")
    init_db(db)
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        resp = TestClient(app).post("/api/scan-custom?universe=hayalet")
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_universes_have_expect_block(tmp_path):
    import sqlite3

    from fastapi.testclient import TestClient

    from opsi.api import app, get_db_path
    from opsi.store import init_db

    db = str(tmp_path / "expect.db")
    init_db(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO underlyings(symbol, price, updated_at, asset_type) VALUES (?,?,?,?)",
        ("AAPL", 315.0, "2026-09-09T00:00:00", "stock"),
    )
    con.execute(
        "INSERT INTO underlyings(symbol, price, updated_at, asset_type) VALUES (?,?,?,?)",
        ("SPY", 500.0, "2026-09-09T00:00:00", "etf"),
    )
    con.commit()
    con.close()
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        c = TestClient(app)
        unis = {u["id"]: u for u in c.get("/api/universes").json()["universes"]}
        assert "expect" in unis["dow30"]
        exp = unis["dow30"]["expect"]
        assert exp["of"] >= exp["csp_ok"] >= 0
        assert (exp["csp_ok"] + exp["unknown"]) <= exp["of"]
        assert "as_of" in exp
        presets = c.get("/api/presets").json()
        assert "expect" in presets["nasdaq100_growth"]
    finally:
        app.dependency_overrides.pop(get_db_path, None)
