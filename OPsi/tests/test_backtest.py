# tests/test_backtest.py
import json
import sqlite3

from opsi.backtest import run_attribution, simulate_strategy
from opsi.store import init_db


def _seed_scan(db, strategy="csp", score=50.0, legs=None, expiry="2026-10-16"):
    init_db(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO scans(started_at, status) VALUES (?, ?)", ("2026-09-01T00:00:00", "done")
    )
    sid = con.execute("SELECT id FROM scans").fetchone()[0]
    cid = f"AAA|{expiry}|18|{strategy}"
    con.execute(
        "INSERT OR REPLACE INTO contracts(id,symbol,expiry,strike,right,bid,ask,volume,openInterest,iv,fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (cid, "AAA", expiry, 18.0, "P", 0.5, 0.53, 200, 1000, 0.3, "x"),
    )
    legs_json = json.dumps(
        legs if legs is not None else [{"strike": 18.0, "mid": 0.5, "spot": 20.0}]
    )
    con.execute(
        "INSERT INTO scores(scan_id,contract_id,strategy,score,ret_ann,prob_otm,liq,iv_rank,trend,adj,details,legs)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, cid, strategy, score, 0.1, 0.9, 0.5, 0.5, 0.5, 1.0, "n", legs_json),
    )
    con.commit()
    con.close()
    return sid


def test_attribution_no_data_status(tmp_path):
    db = str(tmp_path / "b0.db")
    init_db(db)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO scans(started_at, status) VALUES (?, ?)", ("x", "done"))
    sid = con.execute("SELECT id FROM scans").fetchone()[0]
    con.commit()
    con.close()
    run_id = run_attribution(db, sid)
    con = sqlite3.connect(db)
    st = con.execute("SELECT status, n FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
    con.close()
    assert st == ("no-data", 0)


def test_attribution_with_mocked_history(monkeypatch, tmp_path):
    from opsi.backtest import attribution

    db = str(tmp_path / "b1.db")
    sid = _seed_scan(db)
    closes = [(f"2026-09-{d:02d}", 20.0) for d in range(1, 10)] + [("2026-10-16", 19.0)]
    monkeypatch.setattr(attribution, "get_history", lambda s, period="1y": closes)
    run_id = run_attribution(db, sid)
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT n, avg_return, win_rate, status FROM backtest_runs WHERE id=?", (run_id,)
    ).fetchone()
    con.close()
    assert row[3] == "done" and row[0] == 1
    # CSP: prim 0.5*100=50, S_T=19 < K=18? hayır → atanmaz → getiri 50/1800
    assert abs(row[1] - 50.0 / 1800) < 1e-9
    assert row[2] == 1.0


def test_attribution_assigned_put_loses(monkeypatch, tmp_path):
    from opsi.backtest import attribution

    db = str(tmp_path / "b2.db")
    # vade geçmişte: hedef = vade günü, kapanış 15 → put atanır
    sid = _seed_scan(db, expiry="2026-09-05")
    closes = [(f"2026-09-{d:02d}", 20.0) for d in range(1, 5)] + [("2026-09-05", 15.0)]
    monkeypatch.setattr(attribution, "get_history", lambda s, period="1y": closes)
    run_id = run_attribution(db, sid)
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT avg_return, win_rate FROM backtest_runs WHERE id=?", (run_id,)
    ).fetchone()
    con.close()
    assert abs(row[0] - (50.0 - 300.0) / 1800) < 1e-9
    assert row[1] == 0.0


def test_simulator_runs_all_strategies():
    closes = [(f"2026-01-{d:02d}", 20.0 + (d % 5) * 0.2) for d in range(1, 40)]
    closes += [("2026-02-09", 15.0), ("2026-02-10", 15.5)] + [
        (f"2026-02-{d:02d}", 20.0) for d in range(11, 28)
    ]
    for strat in ("csp", "covered_call", "bull_put_spread", "iron_condor"):
        out = simulate_strategy("AAA", strat, closes, strike=19.0, dte=30)
        assert out["n"] == len(closes) - 30
        assert 0.0 <= out["win_rate"] <= 1.0
        assert out["max_loss"] <= 0.0


def test_simulator_empty_series():
    out = simulate_strategy("AAA", "csp", [], strike=19.0)
    assert out == {"n": 0, "avg_return": 0.0, "win_rate": 0.0, "max_loss": 0.0}


def test_settle_math_all_plugins():
    from opsi.strategies import STRATEGIES

    csp = STRATEGIES["csp"].settle([{"strike": 18.0, "mid": 0.5}], 19.0)
    assert csp == 50.0
    csp_assigned = STRATEGIES["csp"].settle([{"strike": 18.0, "mid": 0.5}], 15.0)
    assert csp_assigned == -250.0
    cc = STRATEGIES["covered_call"].settle([{"strike": 21.0, "mid": 0.4, "spot": 20.0}], 20.5)
    assert cc == 90.0
    bps = STRATEGIES["bull_put_spread"].settle(
        [{"strike": 18.0, "mid": 0.5}, {"strike": 17.0, "mid": 0.2}], 19.0
    )
    assert bps == 30.0
    ic = STRATEGIES["iron_condor"].settle(
        [
            {"strike": 18.0, "mid": 0.5},
            {"strike": 17.0, "mid": 0.2},
            {"strike": 21.0, "mid": 0.4},
            {"strike": 22.5, "mid": 0.2},
        ],
        19.0,
    )
    assert ic == 50.0
