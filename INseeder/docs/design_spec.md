# INseeder: US Equities Insider Trading & Copy-Trade System
**Design Document & Architecture Specification**  
*Status: Finalized Architecture*

---

## 1. Overview & Objectives

**INseeder** is an automated, real-time US equities insider trading detection, scoring, alerting, and copy-trading system. The system leverages 100% free and official public data sources (primarily SEC EDGAR Form 4 filings, supplemented by OpenInsider, Finviz, and Yahoo Finance) to identify high-conviction transactions by corporate insiders (CEOs, CFOs, Directors, 10%+ owners).

Key capabilities:
1. **Free Real-time Data Ingestion:** Automated polling of the SEC EDGAR RSS/Atom feed for new Form 4 XML filings and scraping OpenInsider/Finviz for historic and cluster-buy screening.
2. **Quantitative Conviction Scoring (0–100):** Weighted multi-factor model that scores each transaction based on insider seniority, transaction size, percentage change in holdings, cluster buying patterns, and discretionary vs. 10b5-1 plan status.
3. **Dynamic Rule & Signal Engine:** Flexible filtering rules configured via UI/API (e.g., minimum score, minimum dollar value, specific roles, open-market purchases only).
4. **Multi-Channel Alerting:** Instant notifications via Telegram bot and Discord webhooks formatted with rich trade cards and direct links to SEC filings.
5. **Flexible Execution & Copy-Trading Engine:**
   - **Internal Paper Broker:** Zero-risk simulation wallet with realistic order execution and PnL tracking.
   - **Alpaca Markets Adapter:** Live and Paper trading via Alpaca REST API.
   - **Interactive Brokers (IBKR) Adapter:** Extensible interface for IBKR Client Portal/TWS order routing.
   - **Execution Modes:** Full Auto-Execution or Semi-Automated (user approval required before dispatching orders).
6. **Modern Dark-Themed Web Terminal:** Real-time ticker stream, conviction leaderboard, dynamic rule builder, and portfolio tracking.

---

## 2. System Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │            Public Data Sources               │
                    │  (SEC EDGAR RSS/XML, OpenInsider, Finviz)    │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │          Data Ingestion Layer                │
                    │   • sec_edgar.py (Form 4 XML Parser)        │
                    │   • openinsider.py (Cluster/Historic)        │
                    │   • market_data.py (Yahoo Finance Context)   │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │          Scoring & Strategy Engine           │
                    │   • scorer.py (0-100 Conviction Score)       │
                    │   • rules.py (Dynamic Filter Evaluator)      │
                    │   • cluster.py (Multi-insider Detection)     │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │           SQLite Storage Layer               │
                    │   • trades, signals, rules, orders, positions│
                    └──────────────────────┬───────────────────────┘
                                           │
                    ┌──────────────────────┴───────────────────────┐
                    ▼                                              ▼
     ┌────────────────────────────┐                 ┌────────────────────────────┐
     │  Alert & Execution Router  │                 │    FastAPI + SSE Server    │
     │  • Notifier (TG / Discord) │                 │  • REST Endpoints          │
     │  • Broker Adapters:        │                 │  • Real-Time Event Stream  │
     │    - Paper Broker (Dry-run)│                 └──────────────┬─────────────┘
     │    - Alpaca (Paper/Live)   │                                │
     │    - IBKR Adapter          │                                ▼
     └────────────────────────────┘                 ┌────────────────────────────┐
                                                    │    Web Dashboard (UI)      │
                                                    │  • Live Feed & Scores      │
                                                    │  • Rule Builder & Control  │
                                                    │  • Paper Portfolio & PnL   │
                                                    └────────────────────────────┘
```

---

## 3. Detailed Component Specifications

### 3.1 Data Ingestion Layer (`inseeder/collectors/`)
* **`sec_edgar.py`**:
  * Polls `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&count=100&output=atom` every 30–60 seconds.
  * Complies with SEC Fair Access policy: sends custom `User-Agent` (e.g., `INseeder admin@inseeder.local`), respects rate limits (max 10 req/sec, throttled to 1-2 req/sec).
  * Downloads and parses Form 4 XML filings:
    - Issuer details: Ticker, Company Name, CIK.
    - Reporting Owner: Name, Relationship (isDirector, isOfficer, isTenPercentOwner, officerTitle).
    - Non-Derivative Transactions: Transaction date, transaction code (`P` for open-market purchase, `S` for sale, `A` for grant/award, `M` for option exercise), shares transacted, price per share, total value, post-transaction shares owned.
    - Footnotes parsing: Detects Rule 10b5-1 planned transaction disclosures.
* **`openinsider.py`**:
  * Fallback and cluster-screener parser. Scrapes `openinsider.com/latest-cluster-buys` and recent CEO/CFO transactions to enrich historical cluster data.
* **`market_data.py`**:
  * Queries Yahoo Finance (via `yfinance` or direct lightweight HTTP API) to obtain current stock price, market cap, and sector.

### 3.2 Scoring & Conviction Model (`inseeder/engine/`)
Every trade receives a **Conviction Score (0–100)**:

| Factor | Condition | Points |
| :--- | :--- | :--- |
| **Seniority / Role** | CEO | +30 |
| | CFO | +25 |
| | Director / Board Member | +15 |
| | 10%+ Beneficial Owner | +10 |
| **Transaction Type** | Code `P` (Open Market Purchase) | Mandatory for high-conviction buy |
| **Dollar Value** | Value $\ge \$1,000,000$ | +35 |
| | Value $\ge \$500,000$ | +25 |
| | Value $\ge \$100,000$ | +15 |
| | Value $\ge \$25,000$ | +5 |
| **Holding Increase** | Shares bought increase position by $\ge 50\%$ | +25 |
| | Shares bought increase position by $\ge 20\%$ | +15 |
| **Cluster Buying** | 2+ insiders buying same stock within 7 days | +30 |
| **Discretionary** | Not part of a scheduled 10b5-1 trading plan | +10 |

*Scores are capped at 100.*

### 3.3 Rule Engine & Signal Generation (`inseeder/engine/rules.py`)
Users can configure dynamic rules with parameters:
- `min_score`: e.g., 70
- `min_value_usd`: e.g., $100,000
- `allowed_roles`: `["CEO", "CFO", "Director"]`
- `transaction_type`: `["P"]` (or include `["S"]` for anomalous sales)
- `auto_execute`: `True` / `False`
- `execution_target`: `"paper"` / `"alpaca"` / `"ibkr"`
- `position_size_usd`: e.g., $5,000 (or % of portfolio)

### 3.4 Execution Engine (`inseeder/execution/`)
* **`broker_base.py` (`IBrokerAdapter`)**:
  * `async def get_account_summary() -> dict`
  * `async def get_positions() -> list[dict]`
  * `async def submit_order(symbol: str, qty: float, side: str, order_type: str = "market") -> dict`
  * `async def cancel_order(order_id: str) -> bool`
* **`paper_broker.py`**:
  * Manages simulated balance (default: $100,000 USD).
  * Fills orders at current market price (from Yahoo Finance / SEC filing price).
  * Tracks realized and unrealized PnL, average entry price, and cash reserves.
* **`alpaca_broker.py`**:
  * Uses Alpaca REST API (keys provided via environment variables: `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `APCA_API_BASE_URL`).
  * Supports fractional shares and market/limit orders.
* **`ibkr_broker.py`**:
  * Adapter scaffold for Interactive Brokers Client Portal API / TWS.
* **`notifier.py`**:
  * Telegram Bot: Sends markdown-formatted messages with ticker, executive name, dollar value, conviction score, cluster details, and SEC filing link.
  * Discord Webhook: Sends structured embeds.

### 3.5 Database Schema (`inseeder/db/`)
SQLite database with the following tables:
1. **`trades`**:
   - `id` (INTEGER PRIMARY KEY)
   - `accession_no` (TEXT UNIQUE)
   - `filing_date` (DATETIME)
   - `trade_date` (DATE)
   - `ticker` (TEXT)
   - `company_name` (TEXT)
   - `insider_name` (TEXT)
   - `insider_title` (TEXT)
   - `is_director` (BOOLEAN), `is_officer` (BOOLEAN), `is_ten_percent` (BOOLEAN)
   - `transaction_code` (TEXT)
   - `shares` (REAL), `price` (REAL), `value` (REAL)
   - `shares_owned_after` (REAL)
   - `is_10b5_1` (BOOLEAN)
   - `sec_url` (TEXT)
   - `created_at` (DATETIME)
2. **`signals`**:
   - `id` (INTEGER PRIMARY KEY)
   - `trade_id` (INTEGER REFERENCES trades(id))
   - `score` (INTEGER)
   - `matched_rule_id` (INTEGER REFERENCES rules(id))
   - `cluster_count` (INTEGER)
   - `details_json` (TEXT)
   - `status` (TEXT: 'new', 'executed', 'skipped', 'failed')
   - `created_at` (DATETIME)
3. **`rules`**:
   - `id` (INTEGER PRIMARY KEY)
   - `name` (TEXT)
   - `is_active` (BOOLEAN)
   - `min_score` (INTEGER)
   - `min_value` (REAL)
   - `allowed_roles` (TEXT JSON)
   - `allowed_types` (TEXT JSON)
   - `auto_execute` (BOOLEAN)
   - `broker_target` (TEXT)
   - `position_size_usd` (REAL)
4. **`orders`**:
   - `id` (INTEGER PRIMARY KEY)
   - `signal_id` (INTEGER REFERENCES signals(id))
   - `broker` (TEXT)
   - `symbol` (TEXT)
   - `side` (TEXT)
   - `qty` (REAL)
   - `fill_price` (REAL)
   - `status` (TEXT)
   - `created_at` (DATETIME)
5. **`positions`**:
   - `id` (INTEGER PRIMARY KEY)
   - `broker` (TEXT)
   - `symbol` (TEXT)
   - `qty` (REAL)
   - `avg_entry_price` (REAL)
   - `current_price` (REAL)
   - `unrealized_pnl` (REAL)
   - `updated_at` (DATETIME)

### 3.6 API & Web Dashboard
* **FastAPI Server**:
  - `GET /api/trades`: Paginated insider trades with filtering.
  - `GET /api/signals`: High-conviction generated signals.
  - `GET /api/rules` & `POST /api/rules`: Rule management.
  - `GET /api/portfolio`: Account summary, active positions, orders, and PnL.
  - `POST /api/orders/execute`: Manual execution of a signal.
  - `GET /api/hyperliquid/markets`: Cross-references live Hyperliquid L1 assets with SEC Form 4 insider trades.
  - `GET /api/stream`: SSE (Server-Sent Events) endpoint broadcasting new trades and signals in real time.
* **Modern Web Dashboard**:
  - Responsive dark-mode interface built with modern CSS and vanilla JS (zero heavy framework dependencies for clean maintainability).
  - Live stream card view with pulse animations on incoming Form 4 filings.
  - Interactive rule builder with instant preview of matching historical trades.
  - Portfolio & simulation tab with balance and equity curves.

---

## 4. Error Handling & Safety Measures

1. **SEC Rate Limiting & Backoff:**
   - Strict 1-request-per-second baseline for SEC EDGAR endpoints.
   - On HTTP 429 or 503, exponential backoff (2s, 4s, 8s, 16s) up to 60s.
2. **Data Validation:**
   - Robust XML parser handling edge-case Form 4 formats (missing price fields, non-standard officer title tags, joint reporting owners).
3. **Execution Guardrails:**
   - Maximum position size cap per stock (e.g., max 15% of portfolio).
   - Daily maximum trade count cap to prevent runaway execution loops.
   - Market hour checks: Orders submitted outside US market hours are staged for market open or flagged.
4. **Notification Resilience:**
   - Telegram/Discord delivery failures are retried once, then logged as warnings without halting trade execution.

---

## 5. Verification & Testing Strategy

1. **Unit Tests (`tests/`):**
   - `test_sec_parser.py`: Tests XML parsing against fixture Form 4 XML files (CEO buy, CFO cluster, 10b5-1 sell, option exercise).
   - `test_scorer.py`: Validates calculation of Conviction Scores across diverse transaction scenarios.
   - `test_rules.py`: Verifies matching logic for various rule filter combinations.
   - `test_paper_broker.py`: Verifies paper wallet buy/sell, PnL calculations, and balance constraints.
   - `test_api.py`: FastAPI endpoint validation including trade queries, portfolio, and Hyperliquid market matching.
2. **Integration Tests:**
   - End-to-end pipeline test from synthetic Form 4 XML -> Trade ingestion -> Scoring -> Rule match -> Signal -> Paper order.
3. **Manual Verification:**
   - Run worker against live SEC EDGAR RSS feed to confirm real-time ingestion and display in the Web Dashboard.
