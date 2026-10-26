# src/opsi/backtest/attribution.py
"""Live-accumulation attribution: closes past scan positions at expiry price.

Each score row uses legs JSON + underlying price series; results go to the
backtest_runs table. No data means status=no-data, never an exception.
"""

import datetime
import json
import sqlite3

from ..fetch import get_history
from ..logging import get_scan_logger
from ..strategies import STRATEGIES


def run_attribution(
    db: str,
    scan_id: int,
    strategy: str | None = None,
    score_min: float = 0.0,
) -> int:
    """Runs attribution, returns backtest run_id."""
    log = get_scan_logger(f"bt-{scan_id}")
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        started = datetime.datetime.now(datetime.UTC).isoformat()
        cur = con.execute(
            "INSERT INTO backtest_runs(started_at, scan_id, strategy, score_min, n, avg_return, win_rate, status)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (started, scan_id, strategy or "all", score_min, 0, 0.0, 0.0, "running"),
        )
        run_id = cur.lastrowid
        if run_id is None:  # pragma: no cover - INSERT always yields an id
            raise RuntimeError("could not create backtest run record")
        run_id = int(run_id)
        query = (
            "SELECT c.symbol, c.expiry, s.strategy, s.score, s.legs FROM scores s "
            "JOIN contracts c ON c.id=s.contract_id WHERE s.scan_id=? AND s.score>=?"
        )
        params: list[object] = [scan_id, score_min]
        if strategy is not None:
            query += " AND s.strategy=?"
            params.append(strategy)
        rows = con.execute(query, params).fetchall()
        if not rows:
            con.execute("UPDATE backtest_runs SET status='no-data' WHERE id=?", (run_id,))
            con.commit()
            return run_id
        prices: dict[str, list[tuple[str, float]]] = {}
        rets: list[float] = []
        settled_scores: list[float] = []
        for r in rows:
            strat = STRATEGIES.get(r["strategy"])
            if strat is None or not r["legs"]:
                continue
            try:
                legs = json.loads(r["legs"])
            except (TypeError, ValueError):
                continue
            sym = r["symbol"]
            if sym not in prices:
                prices[sym] = get_history(sym, period="1y")
            hist = prices[sym]
            if not hist:
                continue
            target = min(r["expiry"], datetime.datetime.now(datetime.UTC).date().isoformat())
            closes = [c for d, c in hist if d <= target]
            if not closes:
                continue
            spot_t = closes[-1]
            capital = _capital(strat.name, legs)
            if capital <= 0:
                continue
            pnl = strat.settle(legs, spot_t)
            rets.append(pnl / capital)
            settled_scores.append(float(r["score"]))
        if not rets:
            con.execute("UPDATE backtest_runs SET status='no-data' WHERE id=?", (run_id,))
            con.commit()
            log.info("attribution run=%d: no-data", run_id)
            return run_id
        avg_ret = sum(rets) / len(rets)
        win_rate = sum(1 for x in rets if x > 0) / len(rets)
        mean_score = sum(settled_scores) / len(settled_scores)
        con.execute(
            "UPDATE backtest_runs SET n=?, avg_return=?, win_rate=?, status='done',"
            " avg_score=? WHERE id=?",
            (len(rets), avg_ret, win_rate, mean_score, run_id),
        )
        con.commit()
        log.info("attribution run=%d: n=%d avg=%.3f win=%.2f", run_id, len(rets), avg_ret, win_rate)
        return run_id
    finally:
        con.close()


from ..config import DEFAULT_CONTRACT_MULTIPLIER


def _capital(
    strategy: str, legs: list[dict[str, float]], multiplier: int = DEFAULT_CONTRACT_MULTIPLIER
) -> float:
    if strategy == "csp":
        return legs[0]["strike"] * multiplier
    if strategy == "covered_call":
        return legs[0].get("spot", legs[0]["strike"]) * multiplier
    if strategy == "bull_put_spread":
        width = legs[0]["strike"] - legs[1]["strike"]
        return width * multiplier - (legs[0]["mid"] - legs[1]["mid"]) * multiplier
    if strategy == "iron_condor":
        pw = legs[0]["strike"] - legs[1]["strike"]
        cw = legs[3]["strike"] - legs[2]["strike"]
        credit = (legs[0]["mid"] - legs[1]["mid"]) + (legs[2]["mid"] - legs[3]["mid"])
        return max(pw, cw) * multiplier - credit * multiplier
    return 0.0
