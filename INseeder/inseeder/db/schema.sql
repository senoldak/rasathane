-- INseeder Database Schema (SQLite)

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accession_no TEXT UNIQUE NOT NULL,
    filing_date TEXT NOT NULL,
    trade_date TEXT,
    ticker TEXT NOT NULL,
    company_name TEXT,
    insider_name TEXT NOT NULL,
    insider_title TEXT,
    is_director BOOLEAN DEFAULT 0,
    is_officer BOOLEAN DEFAULT 0,
    is_ten_percent BOOLEAN DEFAULT 0,
    transaction_code TEXT NOT NULL,
    shares REAL NOT NULL,
    price REAL,
    value REAL,
    shares_owned_after REAL,
    is_10b5_1 BOOLEAN DEFAULT 0,
    sec_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES trades(id),
    score INTEGER NOT NULL,
    matched_rule_id INTEGER,
    cluster_count INTEGER DEFAULT 1,
    details_json TEXT,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    min_score INTEGER DEFAULT 60,
    min_value REAL DEFAULT 50000,
    allowed_roles TEXT DEFAULT '["CEO","CFO","Director"]',
    allowed_types TEXT DEFAULT '["P"]',
    auto_execute BOOLEAN DEFAULT 0,
    broker_target TEXT DEFAULT 'paper',
    position_size_usd REAL DEFAULT 5000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES signals(id),
    broker TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    fill_price REAL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    avg_entry_price REAL NOT NULL,
    current_price REAL NOT NULL,
    unrealized_pnl REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(broker, symbol)
);

CREATE TABLE IF NOT EXISTS accounts (
    broker TEXT PRIMARY KEY,
    cash REAL NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_filing_date ON trades(filing_date);
CREATE INDEX IF NOT EXISTS idx_signals_score ON signals(score);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_cluster ON trades(ticker, transaction_code, filing_date);
