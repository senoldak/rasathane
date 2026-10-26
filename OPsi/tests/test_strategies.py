# tests/test_strategies.py
from opsi.scorer import core_score
from opsi.strategies import STRATEGIES
from opsi.strategies.covered_call import CoveredCall
from opsi.strategies.csp import CashSecuredPut


def _put_leg(**kw):
    d = {
        "symbol": "AAA",
        "expiry": "2026-10-16",
        "strike": 18.5,
        "bid": 0.5,
        "ask": 0.53,
        "lastPrice": 0.5,
        "volume": 200,
        "openInterest": 1000,
        "mid": 0.515,
        "dte": 20,
        "quoted": True,
        "iv": 0.3,
        "delta": -0.2,
    }
    d.update(kw)
    return d


def test_registry_has_csp_and_cc():
    assert {"csp", "covered_call"} <= set(STRATEGIES)


def test_csp_regression_identical_score():
    csp = CashSecuredPut()
    e = _put_leg()
    assert csp.universe_ok(20.0) is True
    assert csp.universe_ok(25.0) is False
    assert csp.universe_ok(None) is False
    pos = csp.positions([e], 20.0)
    assert len(pos) == 1
    assert pos[0]["capital"] == 1850.0
    assert pos[0]["premium"] == 0.515
    assert csp.score(pos[0], {}) == core_score(e, {})


def test_csp_rejects_35_strike():
    csp = CashSecuredPut()
    assert csp.positions([_put_leg(strike=35.0)], 20.0) == []


def test_covered_call_filters_and_capital():
    cc = CoveredCall()
    assert cc.universe_ok(19.99) is True
    assert cc.universe_ok(20.01) is False
    call = _put_leg(strike=22.0, delta=0.2, bid=0.4, ask=0.44, mid=0.42)
    pos = cc.positions([call], 19.0)
    assert len(pos) == 1
    assert pos[0]["capital"] == 1900.0
    s = cc.score(pos[0], {})
    assert 0 <= s["score"] <= 100


def test_covered_call_rejects_itm_and_wide_delta():
    cc = CoveredCall()
    itm = _put_leg(strike=18.0, delta=0.2)  # strike <= price
    assert cc.positions([itm], 19.0) == []
    wide = _put_leg(strike=22.0, delta=0.5)
    assert cc.positions([wide], 19.0) == []


def test_scan_writes_both_strategies(monkeypatch, tmp_path):
    from opsi import scan
    from opsi.store import init_db

    db = str(tmp_path / "strat.db")
    init_db(db)
    monkeypatch.setattr(scan, "get_price", lambda s: 20.0)
    monkeypatch.setattr(scan, "get_earnings_days", lambda s: None)
    import datetime

    exp = (datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=20)).isoformat()

    def fake_chain(s, right="P"):
        if right == "P":
            return [_put_leg(symbol=s, expiry=exp)]
        return [_put_leg(symbol=s, expiry=exp, strike=22.0, bid=0.19, ask=0.21)]

    monkeypatch.setattr(scan, "get_chain", fake_chain)
    sid = scan.run_full_scan(db, symbols=["AAA"])
    import sqlite3

    con = sqlite3.connect(db)
    strats = sorted(r[0] for r in con.execute("SELECT DISTINCT strategy FROM scores"))
    n = con.execute("SELECT COUNT(*) FROM scores WHERE scan_id=?", (sid,)).fetchone()[0]
    con.close()
    assert strats == ["covered_call", "csp"]
    assert n == 2


def test_api_strategy_filter(tmp_path):
    import sqlite3

    from fastapi.testclient import TestClient

    from opsi.api import app, get_db_path
    from opsi.store import init_db

    db = str(tmp_path / "f.db")
    init_db(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO scans(started_at, status, n_candidates) VALUES (?, ?, ?)", ("x", "done", 2)
    )
    sid = con.execute("SELECT id FROM scans").fetchone()[0]
    con.execute(
        "INSERT OR REPLACE INTO contracts(id,symbol,expiry,strike,right,bid,ask,volume,openInterest,iv,fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("A|2026-10-16|18|csp", "A", "2026-10-16", 18.0, "P", 0.5, 0.5, 9, 9, 0.3, "x"),
    )
    con.execute(
        "INSERT OR REPLACE INTO contracts(id,symbol,expiry,strike,right,bid,ask,volume,openInterest,iv,fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("A|2026-10-16|21|covered_call", "A", "2026-10-16", 21.0, "C", 0.4, 0.4, 9, 9, 0.3, "x"),
    )
    con.execute(
        "INSERT INTO scores(scan_id,contract_id,strategy,score,ret_ann,prob_otm,liq,iv_rank,trend,adj,details)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (sid, "A|2026-10-16|18|csp", "csp", 9.0, 0.1, 0.9, 0.5, 0.5, 0.5, 1.0, "n"),
    )
    con.execute(
        "INSERT INTO scores(scan_id,contract_id,strategy,score,ret_ann,prob_otm,liq,iv_rank,trend,adj,details)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            sid,
            "A|2026-10-16|21|covered_call",
            "covered_call",
            8.0,
            0.1,
            0.9,
            0.5,
            0.5,
            0.5,
            1.0,
            "n",
        ),
    )
    con.commit()
    con.close()
    app.dependency_overrides[get_db_path] = lambda: db
    try:
        c = TestClient(app)
        assert [i["strategy"] for i in c.get("/api/top5").json()["items"]] == [
            "csp",
            "covered_call",
        ]
        only_cc = c.get("/api/top5", params={"strategy": "covered_call"}).json()["items"]
        assert [i["strategy"] for i in only_cc] == ["covered_call"]
        assert c.get("/api/strategies").json() == {
            "strategies": ["bull_put_spread", "covered_call", "csp", "iron_condor"]
        }
    finally:
        app.dependency_overrides.pop(get_db_path, None)
