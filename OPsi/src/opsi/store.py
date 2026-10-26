# src/opsi/store.py
"""SQLite persistence layer: schema + write helpers."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS underlyings(symbol TEXT PRIMARY KEY, price REAL, updated_at TEXT, earnings_date TEXT, iv_history TEXT, asset_type TEXT DEFAULT 'stock');
CREATE TABLE IF NOT EXISTS contracts(id TEXT PRIMARY KEY, symbol TEXT, expiry TEXT, strike REAL, right TEXT, bid REAL, ask REAL, volume INTEGER, openInterest INTEGER, iv REAL, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, status TEXT, finished_at TEXT, duration_s REAL, n_symbols INTEGER DEFAULT 0, n_skipped INTEGER DEFAULT 0, n_candidates INTEGER DEFAULT 0, universe TEXT, n_skip_stale INTEGER DEFAULT 0, n_skip_price INTEGER DEFAULT 0, n_empty_chain INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS scores(scan_id INTEGER, contract_id TEXT, strategy TEXT DEFAULT 'csp', score REAL, ret_ann REAL, prob_otm REAL, liq REAL, iv_rank REAL, trend REAL, adj REAL, details TEXT, legs TEXT, PRIMARY KEY(scan_id, contract_id));
CREATE TABLE IF NOT EXISTS backtest_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, scan_id INTEGER, strategy TEXT, score_min REAL, n INTEGER, avg_return REAL, win_rate REAL, status TEXT, avg_score REAL);
CREATE TABLE IF NOT EXISTS universe_daily(symbol TEXT, date TEXT, close REAL, iv_atm_30d REAL, put_volume INTEGER, put_oi INTEGER, spread_sample REAL, stale_flag INTEGER, PRIMARY KEY(symbol, date));
CREATE TABLE IF NOT EXISTS watchlists(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, symbols TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

_MIGRATIONS = [
    "ALTER TABLE scans ADD COLUMN finished_at TEXT",
    "ALTER TABLE scans ADD COLUMN duration_s REAL",
    "ALTER TABLE scans ADD COLUMN n_symbols INTEGER DEFAULT 0",
    "ALTER TABLE scans ADD COLUMN n_skipped INTEGER DEFAULT 0",
    "ALTER TABLE scans ADD COLUMN n_candidates INTEGER DEFAULT 0",
    "ALTER TABLE scores ADD COLUMN strategy TEXT DEFAULT 'csp'",
    "ALTER TABLE scores ADD COLUMN legs TEXT",
    "CREATE INDEX IF NOT EXISTS idx_scores_scan_score ON scores(scan_id, score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_scores_scan_strategy ON scores(scan_id, strategy, score DESC)",
    "ALTER TABLE underlyings ADD COLUMN earnings_date TEXT",
    "ALTER TABLE underlyings ADD COLUMN iv_history TEXT",
    "ALTER TABLE underlyings ADD COLUMN asset_type TEXT DEFAULT 'stock'",
    "ALTER TABLE backtest_runs ADD COLUMN avg_score REAL",
    "ALTER TABLE scans ADD COLUMN universe TEXT",
    "ALTER TABLE scans ADD COLUMN n_skip_stale INTEGER DEFAULT 0",
    "ALTER TABLE scans ADD COLUMN n_skip_price INTEGER DEFAULT 0",
    "ALTER TABLE scans ADD COLUMN n_empty_chain INTEGER DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS universe_daily(symbol TEXT, date TEXT, close REAL, iv_atm_30d REAL, put_volume INTEGER, put_oi INTEGER, spread_sample REAL, stale_flag INTEGER, PRIMARY KEY(symbol, date))",
    "CREATE TABLE IF NOT EXISTS watchlists(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, symbols TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
]

ContractRow = tuple[str, str, str, float, str, float, float, int, int, float, str]
ScoreRow = tuple[int, str, str, float, float, float, float, float, float, float, str, str]


def init_db(path: str) -> None:
    """Creates schema tables (idempotent), migrates legacy DBs."""
    from pathlib import Path

    parent = Path(path).expanduser().parent
    parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        con.executescript(SCHEMA)
        for sql in _MIGRATIONS:
            try:
                con.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists


def upsert_underlying(
    path: str,
    symbol: str,
    price: float,
    updated_at: str,
    earnings_date: str | None = None,
    iv_history: list[float] | None = None,
    asset_type: str = "stock",
) -> None:
    """Inserts or updates the underlying price; preserves earnings_date/iv_history when None."""
    import json

    hist_json = json.dumps(iv_history[-52:]) if iv_history is not None else None
    with sqlite3.connect(path) as con:
        if hist_json is None:
            con.execute(
                "INSERT INTO underlyings(symbol, price, updated_at, earnings_date, asset_type)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(symbol) DO UPDATE SET price=excluded.price,"
                " updated_at=excluded.updated_at,"
                " earnings_date=COALESCE(excluded.earnings_date, underlyings.earnings_date),"
                " asset_type=COALESCE(excluded.asset_type, underlyings.asset_type)",
                (symbol, price, updated_at, earnings_date, asset_type),
            )
        else:
            con.execute(
                "INSERT INTO underlyings(symbol, price, updated_at, earnings_date, iv_history, asset_type)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(symbol) DO UPDATE SET price=excluded.price,"
                " updated_at=excluded.updated_at,"
                " earnings_date=COALESCE(excluded.earnings_date, underlyings.earnings_date),"
                " iv_history=excluded.iv_history,"
                " asset_type=COALESCE(excluded.asset_type, underlyings.asset_type)",
                (symbol, price, updated_at, earnings_date, hist_json, asset_type),
            )


def insert_contracts(path: str, rows: list[ContractRow]) -> None:
    """Writes contract rows in bulk."""
    with sqlite3.connect(path) as con:
        con.executemany(
            "INSERT OR REPLACE INTO contracts(id, symbol, expiry, strike, right, bid, ask, volume, openInterest, iv, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def create_scan(path: str, started_at: str, status: str = "running") -> int:
    """Opens a new scan record, returns scan_id."""
    with sqlite3.connect(path) as con:
        cur = con.execute(
            "INSERT INTO scans(started_at, status) VALUES (?, ?)",
            (started_at, status),
        )
        if cur.lastrowid is None:  # pragma: no cover - INSERT always yields an id
            raise RuntimeError("could not create scan record")
        return cur.lastrowid


def save_scores(path: str, rows: list[ScoreRow]) -> None:
    """Writes score rows in bulk."""
    with sqlite3.connect(path) as con:
        con.executemany(
            "INSERT OR REPLACE INTO scores(scan_id, contract_id, strategy, score, ret_ann, prob_otm, liq, iv_rank, trend, adj, details, legs)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
