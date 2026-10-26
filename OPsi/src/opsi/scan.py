# src/opsi/scan.py
"""Scan orchestration: universe filter → chain → strategy plugins → SQLite."""

import datetime
import json
import sqlite3
import time
from collections.abc import Callable
from typing import Any

from .academic import apply_academic
from .config import CONTRACT_WEIGHT, RISK_FREE_RATE, STOCK_WEIGHT
from .fetch import (
    atm_put_sample,
    get_chain,
    get_earnings_days,
    get_price,
    get_sp500_symbols,  # noqa: F401 — tests override via monkeypatch (test_scan)
    get_symbols,
    is_etf,
    price_in_usd,
)
from .logging import ScanAdapter, get_scan_logger
from .params import get_params, normalize_params
from .pricer import enrich
from .store import upsert_underlying
from .strategies import STRATEGIES
from .types import AcademicFlags, EnrichedContract, ScoreContext


def _earnings_days_cached(
    con: sqlite3.Connection, db: str, symbol: str, price: float, log: ScanAdapter
) -> int | None:
    """Returns cached earnings-day offset; None when no calendar.

    Three states: future date str (upcoming earnings), "" (checked today,
    none upcoming), NULL/missing (unknown). A cache hit only occurs when the
    stored value is a date after today; "" / past / missing -> refetch and
    overwrite (fresh None -> ""). All errors swallowed with a debug log.
    """
    if is_etf(symbol):
        return None
    today = datetime.datetime.now(datetime.UTC).date()
    today_iso = today.isoformat()
    try:
        row = con.execute(
            "SELECT earnings_date, substr(updated_at, 1, 10) FROM underlyings WHERE symbol=?",
            (symbol,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None  # no earnings_date column (legacy DB)
    if row is not None and row[1] == today_iso and row[0]:
        try:
            cached_date = datetime.date.fromisoformat(row[0])
        except ValueError:
            pass
        else:
            if cached_date > today:
                return (cached_date - today).days
    # Refetch: stored "" / past date / missing / stale row -> fetch fresh and overwrite.
    try:
        edays = get_earnings_days(symbol)
    except Exception:
        log.debug("earnings failed: %s", symbol, exc_info=True)
        return None
    if edays is None:
        log.debug("earnings missing calendar: %s", symbol)
    if edays is not None and edays < 0:
        edays = None  # past earnings: no penalty
    try:
        earnings_date = (
            (today + datetime.timedelta(days=edays)).isoformat() if edays is not None else ""
        )
        upsert_underlying(
            db, symbol, price, datetime.datetime.now(datetime.UTC).isoformat(), earnings_date
        )
    except sqlite3.OperationalError:
        log.debug("earnings cache write failed: %s", symbol, exc_info=True)
    return edays


def _read_iv_history(con: sqlite3.Connection, symbol: str) -> list[float]:
    """Returns symbol IV history (JSON list, max 52 entries); [] when none.

    Legacy DB (no column), empty row, or corrupt JSON -> [].
    """
    try:
        row = con.execute("SELECT iv_history FROM underlyings WHERE symbol=?", (symbol,)).fetchone()
    except sqlite3.OperationalError:
        return []  # no iv_history column (legacy DB)
    if not row or not row[0]:
        return []
    try:
        raw = json.loads(row[0])
    except (ValueError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    hist = [float(v) for v in raw if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return hist[-52:]


def _snapshot_row(con: sqlite3.Connection, symbol: str) -> dict[str, object]:
    """Returns today's universe_daily row as a snapshot dict; {} when none.

    Legacy DB (no table) or missing row for today returns {} — no extra API calls.
    """
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    try:
        row = con.execute(
            "SELECT close, put_volume, put_oi, spread_sample, stale_flag"
            " FROM universe_daily WHERE symbol=? AND date=?",
            (symbol, today),
        ).fetchone()
    except sqlite3.OperationalError:
        return {}
    if row is None:
        return {}
    return {
        "close": row[0],
        "put_volume": row[1],
        "put_oi": row[2],
        "spread_sample": row[3],
        "stale_flag": row[4],
    }


def load_universe(db: str, watchlist: str | None = None, universe: str = "all") -> list[str]:
    """Universe: CSV when watchlist given, registry for preset index id, else legacy all/stocks/etfs."""
    if watchlist:
        import csv

        with open(watchlist, encoding="utf-8") as f:
            return sorted(
                {r["symbol"].strip() for r in csv.DictReader(f) if r.get("symbol", "").strip()}
            )
    return get_symbols(universe)


def is_stale(db: str, symbol: str, days: int = 3) -> bool:
    """True when the last `days` snapshot days all have stale_flag=1."""
    try:
        con = sqlite3.connect(db)
    except sqlite3.Error:
        return False
    try:
        try:
            rows = con.execute(
                "SELECT stale_flag FROM universe_daily WHERE symbol=? ORDER BY date DESC LIMIT ?",
                (symbol, days),
            ).fetchall()
        except sqlite3.OperationalError:
            return False
    finally:
        con.close()
    return len(rows) == days and all(r[0] == 1 for r in rows)


def run_full_scan(
    db: str,
    symbols: list[str] | None = None,
    flags: AcademicFlags | None = None,
    strategies: list[str] | None = None,
    watchlist: str | None = None,
    universe: str = "all",
    params: dict[str, Any] | None = None,
    scan_id: int | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> int:
    """Runs a full scan, returns scan_id. A single-symbol error never stops the scan.

    Uses the active math set from the DB when params is omitted (else defaults).
    Reuses the existing row when scan_id is given (for background scans; the
    caller opens the row with status='running' first).
    Calls progress_cb with (done, total, symbol) on each symbol when given.
    """
    try:
        P = normalize_params(params) if params is not None else get_params(db)
    except Exception:
        P = normalize_params(None)
    merged_flags: dict[str, Any] = {**P["flags"], **(flags or {})}
    active: AcademicFlags = {
        "skew": bool(merged_flags.get("skew", True)),
        "term": bool(merged_flags.get("term", True)),
        "jump": bool(merged_flags.get("jump", True)),
    }
    G = P["general"]
    stock_w = float(G.get("stock_w", STOCK_WEIGHT))
    contract_w = float(G.get("contract_w", CONTRACT_WEIGHT))
    rfr = float(G.get("risk_free", RISK_FREE_RATE))
    wanted = strategies or sorted(STRATEGIES)
    active_strats = [(n, STRATEGIES[n]) for n in wanted if n in STRATEGIES]
    syms = symbols or load_universe(db, watchlist, universe=universe)
    started = time.perf_counter()
    con = sqlite3.connect(db)
    try:
        try:
            con.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error:
            pass
        try:
            con.execute("PRAGMA busy_timeout=5000")
        except sqlite3.Error:
            pass
        sid: Any = scan_id
        if sid is None:
            scan_universe = universe if symbols is None else "custom"
            try:
                sid = con.execute(
                    "INSERT INTO scans(started_at, status, universe) VALUES(?,?,?)",
                    (datetime.datetime.now(datetime.UTC).isoformat(), "running", scan_universe),
                ).lastrowid
            except sqlite3.OperationalError:
                # no universe column (legacy DB): fall back to legacy schema
                sid = con.execute(
                    "INSERT INTO scans(started_at, status) VALUES(?,?)",
                    (datetime.datetime.now(datetime.UTC).isoformat(), "running"),
                ).lastrowid
            con.commit()
        scan_id = int(sid)
        log = get_scan_logger(scan_id)
        log.info(
            "scan started: %d symbols, strategies=%s", len(syms), [n for n, _ in active_strats]
        )
        n_scanned, n_skipped, n_candidates = 0, 0, 0
        n_skip_stale, n_skip_price, n_empty_chain = 0, 0, 0
        total_syms = len(syms)
        for idx, s in enumerate(syms):
            if progress_cb is not None:
                try:
                    progress_cb(idx + 1, total_syms, s)
                except Exception:
                    log.debug("progress_cb failed", exc_info=True)
            try:
                if watchlist is None and is_stale(db, s):
                    n_skipped += 1
                    n_skip_stale += 1
                    log.debug("stale skip %s", s)
                    continue
                px = get_price(s)
                is_etf_sym = is_etf(s)
                # Foreign-exchange (e.g. .IS/TRY) prices are converted to USD for thresholds;
                # raw price is used when the rate is unavailable (no fake rates).
                px_gate = price_in_usd(s, px) if px is not None else None
                interested = [
                    st
                    for _, st in active_strats
                    if st.universe_ok(px_gate, is_etf=is_etf_sym, params=P)
                ]
                if px is None or not interested:
                    n_skipped += 1
                    n_skip_price += 1
                    log.debug("skip %s: price=%s", s, px)
                    continue
                n_scanned += 1
                made = False
                asset_type = "etf" if is_etf_sym else "stock"
                edays = _earnings_days_cached(con, db, s, px, log)
                hist = _read_iv_history(con, s)
                needed_rights = {r for _, st in active_strats for r in st.rights}
                per_right: dict[str, list[EnrichedContract]] = {}
                for right in sorted(needed_rights):
                    enriched: list[EnrichedContract] = []
                    for c in get_chain(s, right):
                        try:
                            e = enrich(c, px, r=rfr, right=right)
                        except Exception:
                            log.debug("enrich failed: %s %s", s, c.get("strike"), exc_info=True)
                            continue
                        # Earnings Layer-1: drop all strategies 0..6 days out
                        # (negative = past earnings → no penalty; other Layer-1
                        #  filters stay in strategies' positions(); full
                        #  passes_filters here assumed put delta and would wrongly
                        #  drop call legs — see
                        #  test_scan_writes_both_strategies.)
                        if edays is not None and 0 <= edays < P["filters"]["earnings_days"]:
                            continue
                        enriched.append(e)
                    per_right[right] = enriched
                # Single IV observation per symbol: mean IV of enriched legs is
                # appended to history (last 52 values), 1 row per symbol is
                # updated — no extra API calls.
                all_ivs = [
                    float(e["iv"])
                    for es in per_right.values()
                    for e in es
                    if isinstance(e.get("iv"), (int, float)) and not isinstance(e.get("iv"), bool)
                ]
                if all_ivs:
                    hist = [*hist, sum(all_ivs) / len(all_ivs)][-52:]
                    try:
                        upsert_underlying(
                            db,
                            s,
                            px,
                            datetime.datetime.now(datetime.UTC).isoformat(),
                            None,
                            hist,
                            asset_type=asset_type,
                        )
                    except sqlite3.OperationalError:
                        log.debug("iv_history write failed: %s", s, exc_info=True)
                ctx: ScoreContext = {
                    "iv_min": 0.15,
                    "iv_max": 0.8,
                    "trend": 0.5,
                    "iv_history": hist,
                    "params": P,
                }
                iv_fallback = len(hist) < 10
                for name, strat in active_strats:
                    if not strat.universe_ok(px_gate, is_etf=is_etf_sym, params=P):
                        continue
                    leg_pool = [e for r in strat.rights for e in per_right.get(r, [])]
                    for pos in strat.positions(leg_pool, px, params=P):
                        try:
                            base = strat.score(pos, ctx, params=P)
                            leg0 = pos["legs"][0]
                            fin = apply_academic(base, {**leg0, "earnings_days": edays}, active, params=P)  # type: ignore[typeddict-unknown-key]
                            snap = _snapshot_row(con, s)
                            snap["earnings_days"] = edays
                            sscore = strat.stock_score(snap)
                            fin["final"] = stock_w * sscore + contract_w * fin["final"]
                            fin["notes"].append(f"stock={sscore:.1f}")
                            if iv_fallback:
                                fin["notes"].append("iv_rank_fallback")
                            leg_key = "_".join(str(leg["strike"]) for leg in pos["legs"])
                            cid = f"{s}|{leg0['expiry']}|{leg_key}|{name}"
                            leg_right = "S" if len(pos["legs"]) > 1 else strat.rights[0]
                            legs_json = json.dumps(
                                [
                                    {
                                        "strike": leg["strike"],
                                        "mid": leg["mid"],
                                        "spot": px,
                                    }
                                    for leg in pos["legs"]
                                ]
                            )
                            now = datetime.datetime.now(datetime.UTC).isoformat()
                            con.execute(
                                "INSERT OR REPLACE INTO contracts(id,symbol,expiry,strike,right,bid,ask,volume,openInterest,iv,fetched_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                (
                                    cid,
                                    s,
                                    leg0["expiry"],
                                    leg0["strike"],
                                    leg_right,
                                    leg0["bid"],
                                    leg0["ask"],
                                    leg0["volume"],
                                    leg0["openInterest"],
                                    leg0["iv"],
                                    now,
                                ),
                            )
                            con.execute(
                                "INSERT OR REPLACE INTO scores(scan_id,contract_id,strategy,score,ret_ann,prob_otm,liq,iv_rank,trend,adj,details,legs) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (
                                    scan_id,
                                    cid,
                                    name,
                                    fin["final"],
                                    fin["ret_ann"],
                                    fin["prob_otm"],
                                    fin["liq"],
                                    fin["iv_rank"],
                                    fin["trend"],
                                    fin["adj"],
                                    ";".join(fin["notes"]),
                                    legs_json,
                                ),
                            )
                            n_candidates += 1
                            made = True
                        except Exception:
                            log.debug("position failed: %s %s", s, name, exc_info=True)
                            continue
                if not made:
                    n_empty_chain += 1
                # Shorten lock time on long scans: periodic intermediate commit.
                if (n_scanned + n_skipped) % 50 == 0:
                    try:
                        con.commit()
                    except sqlite3.Error:
                        pass
            except Exception:
                n_skipped += 1
                log.debug("symbol failed: %s", s, exc_info=True)
                continue
        duration = time.perf_counter() - started
        con.execute(
            "UPDATE scans SET status='done', finished_at=?, duration_s=?, n_symbols=?, n_skipped=?, n_candidates=?, n_skip_stale=?, n_skip_price=?, n_empty_chain=? WHERE id=?",
            (
                datetime.datetime.now(datetime.UTC).isoformat(),
                duration,
                n_scanned,
                n_skipped,
                n_candidates,
                n_skip_stale,
                n_skip_price,
                n_empty_chain,
                scan_id,
            ),
        )
        con.commit()
        log.info(
            "scan done: scanned=%d skipped=%d candidates=%d duration_s=%.1f",
            n_scanned,
            n_skipped,
            n_candidates,
            duration,
        )
    finally:
        con.close()
    return scan_id


def run_snapshot(db: str, symbols: list[str] | None = None, watchlist: str | None = None) -> int:
    """Writes 1 snapshot row per universe symbol; returns rows written."""
    syms = symbols or load_universe(db, watchlist)
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    log = get_scan_logger(f"snap-{today}")
    con = sqlite3.connect(db)
    n = 0
    try:
        for s in syms:
            try:
                px = get_price(s)
                if px is None:
                    log.debug("snapshot skip (no price): %s", s)
                    continue
                try:
                    chains = get_chain(s, "P", max_dte_min=1, max_dte_max=400)
                except TypeError:
                    chains = get_chain(s, "P")  # narrow-signature test double compat
                sm = atm_put_sample(px, chains)
                con.execute(
                    "INSERT OR REPLACE INTO universe_daily(symbol,date,close,iv_atm_30d,put_volume,put_oi,spread_sample,stale_flag)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        s,
                        today,
                        px,
                        sm["iv"],
                        int(sm["volume"]),
                        int(sm["oi"]),
                        sm["spread"],
                        int(sm["stale"]),
                    ),
                )
                n += 1
            except Exception:
                log.debug("snapshot failed: %s", s, exc_info=True)
                continue
        con.commit()
        log.info("snapshot done: %d rows", n)
    finally:
        con.close()
    return n


def top5(db: str, scan_id: int) -> list[dict[str, Any]]:
    """Returns the 5 highest-scoring contracts of a scan."""
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT c.symbol,c.strike,c.expiry,s.score,s.ret_ann FROM scores s JOIN contracts c ON c.id=s.contract_id WHERE s.scan_id=? ORDER BY s.score DESC LIMIT 5",
            (scan_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
