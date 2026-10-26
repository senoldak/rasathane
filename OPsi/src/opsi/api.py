# src/opsi/api.py
"""Read-only FastAPI: top-5, candidates list, dashboard."""

import datetime
import re
import sqlite3
import threading
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import CURATED_PRESETS, DB_PATH
from .schemas import (
    AttributionResponse,
    CandidatesResponse,
    HealthResponse,
    Top5Response,
    WatchlistIn,
    WatchlistOut,
)
from .store import init_db
from .strategies import STRATEGIES

# Run DB schema migrations automatically on startup so database is always up-to-date.
# Stale running scans are marked interrupted here (a dead process leaves status='running').
try:
    init_db(DB_PATH)
    with sqlite3.connect(DB_PATH) as _con:
        _con.execute(
            "UPDATE scans SET status='interrupted', finished_at=? WHERE status='running'",
            (datetime.datetime.now(datetime.UTC).isoformat(),),
        )
except Exception:
    pass

# Arka plan tarama durumu: tek seferde tek tarama; poller buradan okur
_SCAN_LOCK = threading.Lock()
_SCAN_STATE: dict[str, Any] = {
    "running": False,
    "scan_id": None,
    "done": 0,
    "total": 0,
    "symbol": "",
    "universe": "",
}

app = FastAPI(title="OPsi")
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
if not _STATIC_DIR.is_dir() and Path("static").is_dir():
    _STATIC_DIR = Path("static")
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def get_db_path() -> str:
    """Production DB path; tests override via dependency_overrides."""
    return DB_PATH


DbPath = Annotated[str, Depends(get_db_path)]


def _connect(db: str) -> sqlite3.Connection:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout=5000")
    except sqlite3.Error:
        pass
    return con


def _stock_from_details(details: str | None) -> float | None:
    m = re.search(r"stock=([0-9.]+)", details or "")
    return float(m.group(1)) if m else None


import json


def _compute_blueprint_metrics(
    strategy: str, strike: float, bid: float | None, ask: float | None, legs_raw: str | None
) -> dict[str, Any]:
    legs: list[dict[str, float]] = []
    if legs_raw:
        try:
            legs = json.loads(legs_raw)
        except Exception:
            legs = []

    mid = (
        0.5 * (bid + ask) if (bid is not None and ask is not None and bid > 0 and ask > 0) else 0.0
    )
    max_profit = None
    max_loss = None
    breakeven = None

    if strategy == "csp":
        prem = legs[0]["mid"] if legs else mid
        k = strike
        max_profit = round(prem * 100, 2)
        max_loss = round((k - prem) * 100, 2)
        breakeven = round(k - prem, 2)
    elif strategy == "covered_call":
        prem = legs[0]["mid"] if legs else mid
        spot = legs[0].get("spot", strike) if legs else strike
        k = strike
        max_profit = round((k - spot + prem) * 100, 2)
        max_loss = round((spot - prem) * 100, 2)
        breakeven = round(spot - prem, 2)
    elif strategy == "bull_put_spread" and len(legs) >= 2:
        ps, pl = legs[0], legs[1]
        credit = ps["mid"] - pl["mid"]
        width = ps["strike"] - pl["strike"]
        max_profit = round(credit * 100, 2)
        max_loss = round((width - credit) * 100, 2)
        breakeven = round(ps["strike"] - credit, 2)
    elif strategy == "iron_condor" and len(legs) >= 4:
        ps, pl, cs, cl = legs[0], legs[1], legs[2], legs[3]
        credit = (ps["mid"] - pl["mid"]) + (cs["mid"] - cl["mid"])
        pw = ps["strike"] - pl["strike"]
        cw = cl["strike"] - cs["strike"]
        max_profit = round(credit * 100, 2)
        max_loss = round((max(pw, cw) - credit) * 100, 2)
        # Lower and upper break-even points
        breakeven = round(ps["strike"] - credit, 2)

    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakeven": breakeven,
        "legs": legs if legs else None,
    }


def _format_row(r: Any) -> dict[str, Any]:
    d = dict(r)
    legs_raw = d.pop("legs", None)
    bp = _compute_blueprint_metrics(
        d.get("strategy", "csp"), d.get("strike", 0.0), d.get("bid"), d.get("ask"), legs_raw
    )
    return {
        **d,
        "stock_score": _stock_from_details(d.get("details")),
        **bp,
    }


@app.get("/api/top5", response_model=Top5Response)
def top5_api(
    db: DbPath,
    scan_id: int | None = None,
    strategy: str | None = None,
    asset_type: str | None = None,
) -> dict[str, Any]:
    try:
        con = _connect(db)
        try:
            if scan_id is None:
                latest = con.execute(
                    "SELECT id FROM scans WHERE status='done' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if latest is None:
                    return {"as_of": None, "delayed": True, "items": []}
                latest_id = int(latest["id"])
                row = con.execute(
                    "SELECT id FROM scans WHERE status='done' AND n_candidates>0 ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row is None:
                    return {
                        "as_of": latest_id,
                        "as_of_is_latest": False,
                        "delayed": True,
                        "items": [],
                    }
                scan_id = int(row["id"])
                picked_is_latest = scan_id == latest_id
            else:
                picked_is_latest = True
            query = (
                "SELECT c.symbol,c.strike,c.expiry,s.strategy,c.bid,c.ask,s.score,s.ret_ann,"
                "s.prob_otm,s.liq,s.iv_rank,s.trend,s.adj,s.details,s.legs,"
                "COALESCE(u.asset_type, 'stock') as asset_type FROM scores s "
                "JOIN contracts c ON c.id=s.contract_id "
                "LEFT JOIN underlyings u ON u.symbol=c.symbol WHERE s.scan_id=?"
            )
            params: list[Any] = [scan_id]
            if strategy is not None:
                query += " AND s.strategy=?"
                params.append(strategy)
            if asset_type and asset_type != "all":
                if asset_type == "stock":
                    query += " AND COALESCE(u.asset_type, 'stock') = 'stock'"
                elif asset_type == "etf":
                    query += " AND u.asset_type = 'etf'"
            query += " ORDER BY s.score DESC LIMIT 5"
            rows = con.execute(query, params).fetchall()
        finally:
            con.close()
    except sqlite3.OperationalError:
        return {"as_of": None, "delayed": True, "items": []}
    return {
        "as_of": scan_id,
        "as_of_is_latest": picked_is_latest,
        "delayed": True,
        "notice": "15-min delayed data",
        "items": [_format_row(r) for r in rows],
    }


@app.get("/api/candidates", response_model=CandidatesResponse)
def candidates(
    db: DbPath,
    scan_id: int,
    strategy: str | None = None,
    asset_type: str | None = None,
    limit: int = Query(default=300, ge=1, le=1500),
    per_symbol_limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    try:
        con = _connect(db)
        try:
            # Balanced distribution: pull each symbol's top-N contracts, then rank globally,
            # so 1-2 symbols can't fill the whole limit and every scanned name stays visible.
            where_clauses = ["s.scan_id = ?"]
            params: list[Any] = [scan_id]

            if strategy is not None:
                where_clauses.append("s.strategy = ?")
                params.append(strategy)
            if asset_type and asset_type != "all":
                if asset_type == "stock":
                    where_clauses.append("COALESCE(u.asset_type, 'stock') = 'stock'")
                elif asset_type == "etf":
                    where_clauses.append("u.asset_type = 'etf'")

            where_str = " AND ".join(where_clauses)
            query = f"""
                WITH ranked AS (
                    SELECT c.symbol, c.strike, c.expiry, s.strategy, c.bid, c.ask, s.score, s.ret_ann,
                           s.prob_otm, s.liq, s.iv_rank, s.trend, s.adj, s.details, s.legs,
                           COALESCE(u.asset_type, 'stock') as asset_type,
                           ROW_NUMBER() OVER (PARTITION BY c.symbol ORDER BY s.score DESC) as rn
                    FROM scores s
                    JOIN contracts c ON c.id = s.contract_id
                    LEFT JOIN underlyings u ON u.symbol = c.symbol
                    WHERE {where_str}
                )
                SELECT symbol, strike, expiry, strategy, bid, ask, score, ret_ann,
                       prob_otm, liq, iv_rank, trend, adj, details, legs, asset_type
                FROM ranked
                WHERE rn <= ?
                ORDER BY score DESC
                LIMIT ?
            """
            params.extend([per_symbol_limit, limit])
            rows = con.execute(query, params).fetchall()
        finally:
            con.close()
    except sqlite3.OperationalError:
        return {"items": []}
    return {"items": [_format_row(r) for r in rows]}


@app.get("/api/strategies")
def strategies() -> dict[str, list[str]]:
    return {"strategies": sorted(STRATEGIES)}


@app.get("/api/health", response_model=HealthResponse)
def health(db: DbPath) -> dict[str, Any]:
    try:
        con = _connect(db)
        try:
            row = con.execute(
                "SELECT id, status, finished_at, n_candidates FROM scans ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            con.close()
    except sqlite3.OperationalError:
        return {"status": "ok", "delayed": True}
    if row is None:
        return {"status": "ok", "delayed": True}
    return {
        "status": "ok",
        "last_scan_id": int(row["id"]),
        "last_scan_status": row["status"],
        "last_scan_finished_at": row["finished_at"],
        "last_scan_candidates": row["n_candidates"],
        "delayed": True,
    }


@app.get("/api/attribution", response_model=AttributionResponse)
def attribution(
    db: DbPath, strategy: str | None = None, weeks: int = Query(default=12, ge=1, le=104)
) -> dict[str, Any]:
    import datetime

    try:
        con = _connect(db)
        try:
            cutoff = (
                datetime.datetime.now(datetime.UTC) - datetime.timedelta(weeks=weeks)
            ).isoformat()
            query = "SELECT avg_score, n, avg_return, win_rate FROM backtest_runs WHERE started_at>=? AND status='done'"
            params: list[Any] = [cutoff]
            if strategy is not None:
                query += " AND strategy=?"
                params.append(strategy)
            rows = con.execute(query, params).fetchall()
        finally:
            con.close()
    except sqlite3.OperationalError:
        return {"strategy": strategy, "buckets": []}
    if not rows:
        return {"strategy": strategy, "buckets": []}
    bands = [("70-80", 70.0, 80.0), ("80-90", 80.0, 90.0), ("90+", 90.0, 101.0)]
    buckets = []
    for label, lo, hi in bands:
        sel = [r for r in rows if r["avg_score"] is not None and lo <= r["avg_score"] < hi]
        n = sum(r["n"] for r in sel)
        if n < 5:
            buckets.append({"label": label, "n": n, "avg_return": None, "win_rate": None})
            continue
        wret = sum(r["avg_return"] * r["n"] for r in sel) / n
        wwin = sum(r["win_rate"] * r["n"] for r in sel) / n
        buckets.append({"label": label, "n": n, "avg_return": wret, "win_rate": wwin})
    return {"strategy": strategy, "buckets": buckets}


@app.get("/api/presets")
def get_presets(db: DbPath) -> dict[str, Any]:
    """Return non-S&P 500 thematic/index presets (Biotech, Small-Cap, Nasdaq, Semis, etc.)."""
    out: dict[str, Any] = {}
    for key, preset in CURATED_PRESETS.items():
        syms = [str(s) for s in preset.get("symbols", []) if isinstance(s, str) and s.strip()]
        out[key] = {**preset, "expect": _expect_block(db, syms)}
    return out


@app.get("/api/scans")
def recent_scans(db: DbPath, limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    """Return recent scans (with universe label; universe=None on old DBs)."""
    try:
        con = _connect(db)
    except sqlite3.Error:
        return {"scans": []}
    try:
        try:
            rows = con.execute(
                "SELECT id, started_at, status, finished_at, n_symbols, n_skipped,"
                " n_candidates, universe, n_skip_stale, n_skip_price, n_empty_chain"
                " FROM scans ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return {"scans": [dict(r) for r in rows]}
        except sqlite3.OperationalError as exc:
            msg = str(exc)
            if "n_skip_" in msg or "n_empty_chain" in msg:
                try:
                    rows = con.execute(
                        "SELECT id, started_at, status, finished_at, n_symbols, n_skipped,"
                        " n_candidates, universe FROM scans ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                    return {
                        "scans": [
                            {
                                **dict(r),
                                "n_skip_stale": 0,
                                "n_skip_price": 0,
                                "n_empty_chain": 0,
                            }
                            for r in rows
                        ]
                    }
                except sqlite3.OperationalError:
                    pass
            rows = con.execute(
                "SELECT id, started_at, status, finished_at, n_symbols, n_skipped,"
                " n_candidates FROM scans ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return {"scans": [{**dict(r), "universe": None} for r in rows]}
    except sqlite3.OperationalError:
        return {"scans": []}
    finally:
        con.close()


def _expect_block(db: str, symbols: list[str]) -> dict[str, Any]:
    """CSP price-cache expectation: how many symbols pass the CSP universe gate."""
    from .params import get_params
    from .strategies.csp import CashSecuredPut

    syms = sorted({s.strip().upper() for s in symbols if s.strip()})
    if not syms:
        return {"csp_ok": 0, "of": 0, "unknown": 0, "as_of": None}
    params: dict[str, Any] | None
    try:
        params = get_params(db)
    except Exception:
        params = None
    gate = CashSecuredPut()
    csp_ok: int = 0
    unknown: int = 0
    stamps: list[str] = []
    try:
        con = _connect(db)
        try:
            for s in syms:
                row = con.execute(
                    "SELECT price, updated_at, asset_type FROM underlyings WHERE symbol=?", (s,)
                ).fetchone()
                if row is None or row["price"] is None:
                    unknown += 1
                    continue
                stamps.append(str(row["updated_at"]))
                if gate.universe_ok(
                    float(row["price"]), is_etf=(row["asset_type"] == "etf"), params=params
                ):
                    csp_ok += 1
        finally:
            con.close()
    except sqlite3.Error:
        return {"csp_ok": 0, "of": len(syms), "unknown": len(syms), "as_of": None}
    return {
        "csp_ok": csp_ok,
        "of": len(syms),
        "unknown": unknown,
        "as_of": min(stamps) if stamps else None,
    }


def _offline_universe_symbols(uid: str) -> list[str]:
    """Universe symbols without network: static config or the JSON cache file universe_info reads."""
    import json
    from pathlib import Path

    from .config import UNIVERSE_CACHE_DIR, UNIVERSES

    key = (uid or "").lower()
    meta = UNIVERSES[key]
    if meta.get("kind") == "static":
        raw_syms = meta.get("symbols", [])
        return [str(s) for s in raw_syms if isinstance(s, str) and s.strip()]
    try:
        data = json.loads((Path(UNIVERSE_CACHE_DIR) / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    raw_list = data.get("symbols", [])
    if not isinstance(raw_list, list):
        return []
    return [str(s) for s in raw_list if isinstance(s, str) and s.strip()]


@app.get("/api/universes")
def get_universes(db: DbPath) -> dict[str, list[dict[str, Any]]]:
    """Return ready-made index universes (offline; counts from cache/fallback)."""
    from .config import UNIVERSES
    from .fetch import universe_info

    items: list[dict[str, Any]] = []
    for uid in sorted(UNIVERSES):
        info = universe_info(uid)
        info["expect"] = _expect_block(db, _offline_universe_symbols(uid))
        items.append(info)
    return {"universes": items}


@app.get("/api/settings/params")
def get_math_params(db: DbPath) -> dict[str, Any]:
    """Scan math: defaults + active set."""
    from .params import DEFAULT_PARAMS, get_params

    return {"defaults": DEFAULT_PARAMS, "active": get_params(db)}


@app.put("/api/settings/params")
def put_math_params(payload: dict[str, Any], db: DbPath) -> dict[str, Any]:
    """Save validated scan math (used by subsequent scans)."""
    from fastapi import HTTPException

    from .params import DEFAULT_PARAMS, save_params

    body = payload.get("params", payload) if isinstance(payload, dict) else None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid parameter body.")
    try:
        active = save_params(db, body)
    except sqlite3.Error:
        raise HTTPException(status_code=502, detail="Could not save parameters.")
    return {"defaults": DEFAULT_PARAMS, "active": active}


@app.get("/api/watchlists", response_model=list[WatchlistOut])
def get_watchlists(db: DbPath) -> list[dict[str, Any]]:
    con = _connect(db)
    try:
        rows = con.execute(
            "SELECT id, name, symbols, created_at FROM watchlists ORDER BY id ASC"
        ).fetchall()
        result = []
        for r in rows:
            syms = [s.strip().upper() for s in r["symbols"].split(",") if s.strip()]
            result.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "symbols": syms,
                    "created_at": r["created_at"],
                }
            )
        return result
    finally:
        con.close()


@app.post("/api/watchlists", response_model=WatchlistOut)
def create_watchlist(payload: WatchlistIn, db: DbPath) -> dict[str, Any]:
    import datetime

    from fastapi import HTTPException

    clean_syms = sorted({s.strip().upper() for s in payload.symbols if s.strip()})
    if not clean_syms:
        raise HTTPException(status_code=400, detail="At least one valid symbol is required.")

    syms_str = ",".join(clean_syms)
    now = datetime.datetime.now(datetime.UTC).isoformat()

    con = _connect(db)
    try:
        try:
            cur = con.execute(
                "INSERT INTO watchlists(name, symbols, created_at) VALUES(?, ?, ?)",
                (payload.name.strip(), syms_str, now),
            )
            con.commit()
            wid = cur.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409, detail=f"A list named '{payload.name}' already exists."
            )
        return {
            "id": wid,
            "name": payload.name.strip(),
            "symbols": clean_syms,
            "created_at": now,
        }
    finally:
        con.close()


@app.delete("/api/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: int, db: DbPath) -> dict[str, Any]:
    from fastapi import HTTPException

    con = _connect(db)
    try:
        cur = con.execute("DELETE FROM watchlists WHERE id=?", (watchlist_id,))
        con.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="List not found.")
        return {"status": "ok", "deleted_id": watchlist_id}
    finally:
        con.close()


def _run_scan_thread(
    db: str,
    *,
    symbols: list[str] | None,
    universe: str,
    scan_id: int,
) -> None:
    """Background scan worker: reset locked state on completion, mark row failed on error."""
    from .scan import run_full_scan

    def _cb(done: int, total: int, symbol: str) -> None:
        with _SCAN_LOCK:
            _SCAN_STATE.update(done=done, total=total, symbol=symbol)

    try:
        if symbols is None:
            run_full_scan(db, universe=universe, scan_id=scan_id, progress_cb=_cb)
        else:
            run_full_scan(db, symbols=symbols, scan_id=scan_id, progress_cb=_cb)
    except Exception as exc:
        from .logging import get_scan_logger

        get_scan_logger(scan_id).warning("background scan failed: %s", exc)
        try:
            con = _connect(db)
            try:
                con.execute(
                    "UPDATE scans SET status='failed', finished_at=? WHERE id=?",
                    (datetime.datetime.now(datetime.UTC).isoformat(), scan_id),
                )
                con.commit()
            finally:
                con.close()
        except Exception as db_exc:
            get_scan_logger(scan_id).warning("marking scan failed failed: %s", db_exc)
    finally:
        with _SCAN_LOCK:
            if _SCAN_STATE.get("scan_id") == scan_id:
                _SCAN_STATE.update(
                    running=False, scan_id=None, done=0, total=0, symbol="", universe=""
                )


@app.post("/api/scan-custom", status_code=202)
def scan_custom(
    db: DbPath,
    symbols: list[str] = Query(default=[]),
    watchlist_id: int | None = Query(default=None),
    universe: str | None = Query(default=None),
) -> dict[str, Any]:
    """Start a scan for the selected custom list, symbols, or ready-made index universe in the BACKGROUND.

    Return 202 immediately; track progress via GET /api/scans/active. Only one scan at a time.
    """
    from fastapi import HTTPException

    from .config import UNIVERSES
    from .fetch import get_universe_symbols

    target_symbols = [s.strip().upper() for s in symbols if s.strip()]
    universe_label: str | None = None
    if universe is not None:
        key = universe.strip().lower()
        if key not in UNIVERSES:
            raise HTTPException(status_code=400, detail=f"Unknown universe: {universe}")
        try:
            target_symbols.extend(get_universe_symbols(key))
        except Exception:
            raise HTTPException(status_code=502, detail=f"Could not load universe '{key}'.")
        universe_label = key
    if watchlist_id is not None:
        con = _connect(db)
        try:
            row = con.execute(
                "SELECT symbols FROM watchlists WHERE id=?", (watchlist_id,)
            ).fetchone()
            if row:
                target_symbols.extend(
                    [s.strip().upper() for s in row["symbols"].split(",") if s.strip()]
                )
        finally:
            con.close()

    target_symbols = sorted(set(target_symbols))
    if not target_symbols:
        raise HTTPException(status_code=400, detail="No symbols to scan.")

    universe_only = universe_label is not None and not symbols and watchlist_id is None
    with _SCAN_LOCK:
        if _SCAN_STATE["running"]:
            raise HTTPException(status_code=409, detail="A scan is already running.")
        con = _connect(db)
        try:
            try:
                cur = con.execute(
                    "INSERT INTO scans(started_at, status, universe) VALUES(?,?,?)",
                    (
                        datetime.datetime.now(datetime.UTC).isoformat(),
                        "running",
                        universe_label if universe_only else "custom",
                    ),
                )
            except sqlite3.OperationalError:
                cur = con.execute(
                    "INSERT INTO scans(started_at, status) VALUES(?,?)",
                    (datetime.datetime.now(datetime.UTC).isoformat(), "running"),
                )
            sid = int(cur.lastrowid or 0)
            con.commit()
        finally:
            con.close()
        _SCAN_STATE.update(
            running=True,
            scan_id=sid,
            done=0,
            total=len(target_symbols),
            symbol="",
            universe=universe_label or "custom",
        )
    thread = threading.Thread(
        target=_run_scan_thread,
        kwargs={
            "db": db,
            "symbols": None if universe_only else target_symbols,
            "universe": universe_label or "all",
            "scan_id": sid,
        },
        daemon=True,
    )
    thread.start()
    return {"status": "ok", "scan_id": sid, "symbols_count": len(target_symbols)}


@app.get("/api/scans/active")
def scan_active() -> dict[str, Any]:
    """Return running scan progress, or running=false when idle (for poller)."""
    with _SCAN_LOCK:
        return dict(_SCAN_STATE)


NAV_ITEMS = (
    ("panel", "Panel"),
    ("universes", "Universes"),
    ("lists", "Lists"),
    ("settings", "Settings"),
)


def _nav(active: str) -> str:
    links = "".join(
        f'<a href="/{slug}" class="page-nav-link{" is-active" if slug == active else ""}"'
        + (f' aria-current="page">{label}</a>' if slug == active else f">{label}</a>")
        for slug, label in NAV_ITEMS
    )
    return f'<nav class="page-nav" aria-label="Pages">{links}</nav>'


def shell(active: str) -> str:
    refresh_btn = (
        '      <button id="btn-refresh" class="btn-action" aria-label="Refresh data">'
        '        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>'
        "        Refresh"
        "      </button>"
        if active == "panel"
        else ""
    )
    strategy_bar = (
        '  <nav class="strategy-bar" id="strats" role="navigation" aria-label="Option Strategy Filter"></nav>'
        if active == "panel"
        else ""
    )
    main_html = (
        '  <main class="terminal-body split-cockpit-body">'
        "    <!-- LEFT COLUMN: Candidate Screener Table -->"
        '    <section class="section-screener split-left-pane" aria-labelledby="screener-heading">'
        '      <div class="screener-header">'
        "        <div>"
        '          <h2 id="screener-heading" class="section-title">Opportunities Screener</h2>'
        '          <span class="section-subtitle" id="candidate-count">Scanning database...</span>'
        "        </div>"
        '        <div class="screener-controls">'
        '          <button id="btn-toggle-group" class="btn-group-toggle active" title="Group by symbol (best contract on top)">'
        '            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>'
        "            <span>Grouped View</span>"
        "          </button>"
        '          <div class="asset-filter-group" id="asset-type-filters" role="group" aria-label="Asset Type">'
        '            <button class="asset-pill active" data-type="all">All</button>'
        '            <button class="asset-pill" data-type="stock">Stocks</button>'
        '            <button class="asset-pill" data-type="etf">ETFs</button>'
        "          </div>"
        '          <div class="search-box">'
        '            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
        '            <input type="text" id="filter-search" placeholder="Filter symbol (e.g. SPY, AAPL)..." aria-label="Search symbol">'
        "          </div>"
        "        </div>"
        "      </div>"
        '      <div id="tbl" class="table-container"></div>'
        "    </section>"
        "    <!-- RIGHT COLUMN: Interactive Detail Inspector -->"
        '    <aside class="section-inspector split-right-pane" id="inspector-panel" aria-label="Contract Breakdown & Blueprint">'
        '      <div id="inspector-content" class="inspector-content">'
        '        <div class="inspector-placeholder">'
        '          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:0.4; margin-bottom:12px;"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M9 21V9"/></svg>'
        '          <p style="font-weight:500; font-size:0.95rem; color:var(--text-secondary);">Select an opportunity to see details</p>'
        '          <small style="color:var(--text-muted);">Click a row in the table on the left to inspect the payoff diagram, order draft, and 6-factor breakdown.</small>'
        "        </div>"
        "      </div>"
        "    </aside>"
        "  </main>"
        if active == "panel"
        else ""
    )
    universes_html = (
        '  <section id="page-universes" class="page-lists">'
        '    <div class="lists-page-head">'
        "      <div>"
        '        <h2 class="section-title">Scan Universes</h2>'
        '        <span class="section-subtitle">Ready-made index universes and thematic presets — scan with one click</span>'
        "      </div>"
        "    </div>"
        '        <div class="lists-section">'
        '          <h3 class="lists-section-title">Ready-Made Index Universes</h3>'
        '          <p class="modal-desc" style="margin-bottom:12px;">Scan Nasdaq 100, Dow 30, Russell 2000 liquid subset, sector ETFs, or BIST 30 with one click:</p>'
        '          <div id="universe-items-list" class="watchlist-cards-grid"></div>'
        "        </div>"
        '        <div class="lists-section">'
        '          <h3 class="lists-section-title">Non-S&P 500 Thematic & Index Universes</h3>'
        '          <p class="modal-desc" style="margin-bottom:12px;">Scan Biotech, Russell 2000, Semiconductors, or Nasdaq growth stocks with one click, or add them to your list:</p>'
        '          <div id="preset-items-list" class="watchlist-cards-grid"></div>'
        "        </div>"
        "  </section>"
        if active == "universes"
        else ""
    )
    lists_html = (
        '  <section id="page-lists" class="page-lists">'
        '    <div class="lists-page-head">'
        "      <div>"
        '        <h2 class="section-title">My Lists</h2>'
        '        <span class="section-subtitle">Custom lists and recent scans — scan with one click</span>'
        "      </div>"
        "    </div>"
        '        <div class="lists-section">'
        '          <h3 class="lists-section-title">My Lists</h3>'
        '          <p class="modal-desc">Create custom stock/ETF lists for your strategy and scan them with one click.</p>'
        '          <div class="watchlist-form">'
        '            <div class="input-row">'
        '              <input type="text" id="wl-name-input" placeholder="List Name (e.g. High Volatility)" class="input-styled">'
        '              <input type="text" id="wl-syms-input" placeholder="Symbols, comma-separated (e.g. NVDA, AAPL)" class="input-styled" style="flex:2;">'
        '              <button id="btn-create-wl" class="btn-action btn-primary-accent">+ Add List</button>'
        "            </div>"
        "          </div>"
        '          <div id="watchlist-items-list" class="watchlist-cards-grid"></div>'
        "        </div>"
        '        <div class="lists-section">'
        '          <h3 class="lists-section-title">Recent Scans</h3>'
        '          <div id="recent-scans-list" class="watchlist-cards-grid"></div>'
        "        </div>"
        "  </section>"
        if active == "lists"
        else ""
    )
    settings_html = (
        '  <section id="page-settings" class="page-lists">'
        '    <div class="lists-section">'
        '      <h3 class="lists-section-title">Scan Math</h3>'
        '      <p class="modal-desc" style="margin-bottom:4px;">Thresholds, score weights, and academic multipliers. Your saved set is stored in the database and used by subsequent scans.</p>'
        '      <div id="math-settings" class="math-grid"></div>'
        '      <div class="math-actions">'
        '        <span id="math-weight-note" class="scan-meta"></span>'
        '        <span style="flex:1;"></span>'
        '        <button id="btn-math-reset" class="btn-action">Reset to Defaults</button>'
        '        <button id="btn-math-save" class="btn-action btn-primary-accent">Save</button>'
        "      </div>"
        "    </div>"
        "  </section>"
        if active == "settings"
        else ""
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>OPsi — Institutional Options Cockpit</title>"
        "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230e1424'/%3E%3Ctext x='32' y='42' font-family='Arial,sans-serif' font-size='28' font-weight='bold' text-anchor='middle' fill='%2310b981'%3EOP%3C/text%3E%3C/svg%3E\">"
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">'
        '<link rel="stylesheet" href="/static/style.css"></head><body>'
        '<div class="terminal-layout"><div id=app>'
        '  <header class="terminal-header">'
        '    <div class="brand-group">'
        '      <div class="logo-mark"><span class="logo-accent">OP</span>si</div>'
        '      <div class="status-indicator" id="scan-status-pill">'
        '        <span class="status-dot"></span>'
        '        <span id="scan-status-text">Scanning market...</span>'
        "      </div>"
        "    </div>"
        '    <div class="header-actions">'
        '      <span class="badge-delay" title="Market data is delayed by 15 minutes">15-min delayed</span>'
        + refresh_btn
        + "    </div>"
        + _nav(active)
        + "  </header>"
        '  <div id="scan-progress" class="scan-progress" hidden>'
        '    <div class="scan-progress-track"><div class="scan-progress-fill" id="scan-progress-fill"></div></div>'
        '    <span class="scan-progress-text" id="scan-progress-text"></span>'
        "  </div>"
        '  <div id="scan-toast" class="scan-toast" hidden></div>'
        + strategy_bar
        + main_html
        + universes_html
        + lists_html
        + settings_html
        + '  <footer class="terminal-footer">'
        "    <span>OPsi Options Engine · Multi-layer academic scoring (IV Rank, Skew, Liquidity, Trend, Kelly sizing)</span>"
        '    <span class="disclaimer">Delayed market data for quantitative research only. Not financial advice.</span>'
        "  </footer>"
        "</div></div>"
        '<script src="/static/app.js?v=7"></script></body></html>'
    )


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/panel", status_code=307)


@app.get("/panel", response_class=HTMLResponse)
def page_panel() -> str:
    return shell("panel")


@app.get("/universes", response_class=HTMLResponse)
def page_universes() -> str:
    return shell("universes")


@app.get("/lists", response_class=HTMLResponse)
def page_lists() -> str:
    return shell("lists")


@app.get("/settings", response_class=HTMLResponse)
def page_settings() -> str:
    return shell("settings")
