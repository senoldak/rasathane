# biOF — Institutional-Grade Biotech Financial Intelligence Terminal

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B%20Async-d71f00.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/tests-23%20passed%20%7C%2077%25%20coverage-brightgreen.svg)](#testing)
[![Interface](https://img.shields.io/badge/UI-Dark%20Cyber--Biotech%20Terminal-00f59b.svg)](#terminal-frontend)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#license)

**biOF** (Bio-Alpha Terminal) is an institutional-grade biotech financial intelligence platform and quantitative catalyst scoring engine. In the biopharmaceutical sector, enterprise valuation is overwhelmingly driven by discrete, binary clinical and regulatory milestones—FDA PDUFA target action dates, Phase 1/2/3 trial readouts, AdCom panel votes, and Complete Response Letters (CRLs)—rather than conventional quarterly financial metrics.

biOF aggregates clinical and regulatory data across US-listed biopharmaceutical equities (NASDAQ/NYSE), computes a multi-factor risk/reward score (**Bio-Alpha Score**, $0 \dots 100$), detects dilution hazards before event windows, and visualizes market intelligence through a high-density, Bloomberg-style dark cyber-biotech terminal interface.

---

## Key Features

- **Multi-Source Asynchronous Data Ingestion Engine:**
  - **ClinicalTrials.gov API v2:** Fetches interventional studies, parses milestone dates, enrollment sizes, arm interventions, and recruitment statuses with fallback support for nested study design schemas.
  - **openFDA Drug Approvals (`Drugs@FDA`):** Ingests NDA/BLA approvals, supplements, 510(k) clearances, and regulatory designations with date-sorted submission tracking.
  - **Market & Financial Telemetry (`yfinance`):** Extracts market capitalization, enterprise value, cash reserves, and quarterly burn rates; computes cash runway projections.
  - **Collector Resiliency:** Implements an asynchronous token-bucket rate limiter (5 Hz default) with exponential backoff and jitter against HTTP 429 and 5xx responses.
- **Quantitative Bio-Alpha Scoring Engine ($0 \dots 100$):**
  - **Catalyst Proximity & Velocity ($S_{\text{prox}}$):** Exponential time-decay model ($\tau = 30$ days) prioritizing near-term binary events while assigning zero weight to past milestones.
  - **Historical Probability of Success ($S_{\text{pos}}$):** Empirical phase transition benchmarks across Oncology, Neurology/CNS, Rare Diseases/Hematology, Immunology, and Infectious Diseases, augmented with regulatory designation modifiers (Breakthrough Therapy, Priority Review, Fast Track, Orphan Drug).
  - **Asymmetric Payoff ($S_{\text{asym}}$):** Continuous evaluation of Target Addressable Market (TAM) relative to enterprise valuation.
  - **Dilution Hazard Warning System ($S_{\text{fin}}$):** Automated detection and visual alerting for micro/small-cap biotechs operating with less than 6 months of cash runway prior to catalyst readouts.
- **Dark Cyber-Biotech Terminal UI:**
  - High-density Bloomberg-inspired interface styled in `#0a0e17` slate, `#00f59b` emerald approvals, `#ff3366` crimson CRLs, and `#ffb800` amber countdowns.
  - Continuous streaming regulatory news ticker marquee with color-coded catalyst tags.
  - Real-time KPI summary bar tracking active assets, 30-day PDUFA decisions, high-alpha setups, and active dilution alerts.
  - Interactive multi-variable Catalyst Calendar & Bio-Alpha Screener.
  - Comprehensive Company Pipeline Dossier with multi-stage clinical progress tracks and direct ClinicalTrials.gov study links.
  - Zero-build client stack: Pure Vanilla ES6, CSS variables, and HTML5 served directly by FastAPI without Node.js dependencies.

---

## Architecture & System Design

biOF is built on an asynchronous event-driven architecture using Python 3.10+, FastAPI, SQLAlchemy 2.0 Async ORM, and hybrid database persistence (SQLite via `aiosqlite` with WAL mode and foreign key enforcement by default, with native PostgreSQL support via `DATABASE_URL`).

### High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph DataIngestion [Multi-Source Ingestion Layer]
        CT[ClinicalTrials.gov API v2] --> BaseCol[BaseCollector: Token Bucket + Backoff]
        FDA[openFDA Drugs@FDA API] --> BaseCol
        YF[Yahoo Finance Market Data] --> MktCol[MarketDataCollector: Thread Pool]
    end

    subgraph CoreEngine [Quantitative Intelligence Engine]
        BaseCol --> IngestPipeline[Normalization & Entity Resolution]
        MktCol --> IngestPipeline
        IngestPipeline --> BioAlphaEngine[Bio-Alpha Scoring Calculator]
        
        BioAlphaEngine --> Prox[Proximity: S_prox]
        BioAlphaEngine --> PoS[PoS Benchmark Matrix: S_pos]
        BioAlphaEngine --> Asym[TAM / Cap Payoff: S_asym]
        BioAlphaEngine --> Fin[Cash Runway & Dilution: S_fin]
    end

    subgraph Persistence [Database Layer: SQLAlchemy 2.0 Async]
        BioAlphaEngine --> DB[(SQLite WAL / PostgreSQL)]
        DB --> Models[Companies / Drugs / Trials / Catalysts / Scores]
    end

    subgraph Delivery [API & Presentation Layer]
        DB --> API[FastAPI REST API: /api/v1/*]
        API --> Docs[Swagger / ReDoc OpenAPI Docs]
        API --> Terminal[Dark Cyber-Biotech Terminal: Vanilla HTML5 / ES6 / CSS]
    end
```

### Data Flow Diagram

```mermaid
flowchart LR
    ExternalData[Upstream APIs] --> Collector[Rate-Limited Collector]
    Collector --> ModelInit[ORM Entities Persisted]
    ModelInit --> ScoreCalc[calculate_bio_alpha]
    ScoreCalc --> ScoreModel[BioAlphaScore Persisted]
    ScoreModel --> RestEndpoints[REST Endpoints: /catalysts, /screener]
    RestEndpoints --> BrowserUI[Terminal UI Grid & Dossier Modal]
```

---

## Mathematical Formulation: Bio-Alpha Score

The composite Bio-Alpha Score ($0 \le S \le 100$) represents the risk-adjusted expected return of a biotechnology equity approaching a catalyst window:

$$S_{\text{composite}} = \frac{w_1 S_{\text{prox}} + w_2 S_{\text{pos}} + w_3 S_{\text{asym}} + w_4 S_{\text{fin}} + w_5 S_{\text{smart}}}{w_1 + w_2 + w_3 + w_4 + w_5}$$

Where default weights are: $w_1 = 0.25$, $w_2 = 0.25$, $w_3 = 0.20$, $w_4 = 0.20$, $w_5 = 0.10$.

### 1. Catalyst Proximity & Velocity ($S_{\text{prox}}$)

Exponential time-decay model centered on catalyst target date:

$$S_{\text{prox}}(\Delta t) = \begin{cases} 0.0 & \text{if } \Delta t < 0 \text{ (past events)} \\ 100.0 & \text{if } \Delta t \in \{0, 1\} \\ 100.0 \cdot \exp\left(-\frac{\Delta t - 1}{\tau}\right) & \text{if } \Delta t > 1 \end{cases}$$

Where $\tau = 30.0$ days. Key benchmark values:
- $T-0$ to $T-1$: $S_{\text{prox}} = 100.0$
- $T-7$: $S_{\text{prox}} \approx 81.9$
- $T-14$: $S_{\text{prox}} \approx 64.9$
- $T-30$: $S_{\text{prox}} \approx 38.0$
- $T-90$: $S_{\text{prox}} \approx 5.1$

### 2. Historical Probability of Success ($S_{\text{pos}}$)

Empirical phase transition probability benchmarks mapped by therapeutic area and development stage:

| Therapeutic Area | Preclinical | Phase 1 | Phase 2 | Phase 3 | PDUFA / NDA / BLA | Approved |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Oncology** | 2.0% | 5.0% | 18.0% | 45.0% | 88.0% | 95.0% |
| **Neurology / CNS** | 2.0% | 8.0% | 15.0% | 48.0% | 85.0% | 95.0% |
| **Rare Disease / Hematology** | 3.0% | 22.0% | 38.0% | 68.0% | 93.0% | 98.0% |
| **Immunology / Autoimmune** | 2.5% | 12.0% | 25.0% | 55.0% | 89.0% | 96.0% |
| **Infectious Disease** | 2.5% | 14.0% | 28.0% | 62.0% | 90.0% | 96.0% |
| **General Default** | 2.0% | 10.0% | 22.0% | 52.0% | 88.0% | 95.0% |

Regulatory Designation Boosts added to base score:
- **Breakthrough Therapy:** $+10.0$
- **Priority Review:** $+5.0$
- **Orphan Drug:** $+4.0$
- **Fast Track:** $+3.0$

### 3. Asymmetric Payoff ($S_{\text{asym}}$)

Continuous function comparing Target Addressable Market ($\text{TAM}$) to Market Capitalization:

$$\text{Ratio} = \frac{\text{TAM (\text{USD M})}}{\max(\text{MarketCap (\text{USD M})}, 10.0)}$$

$$S_{\text{asym}} = \min\left(100.0, \max\left(0.0, \frac{\text{Ratio}}{5.0} \times 100.0\right)\right)$$

A $5.0\times$ TAM-to-market-cap ratio achieves the maximum score of $100.0$.

### 4. Financial Health & Dilution Hazard ($S_{\text{fin}}$)

Calculated from cash runway in months:

$$\text{Runway} = \frac{\text{Cash and Short-Term Investments (\text{USD M})}}{\max\left(\frac{\text{Quarterly Burn (\text{USD M})}}{3}, 0.01\right)}$$

- $\text{Runway} < 6\text{ months}$: $S_{\text{fin}} = \max\left(0.0, \frac{\text{Runway}}{6.0} \times 25.0\right)$, with **`dilution_flag = True`** (triggers ⚠️ DILUTION RISK alert).
- $6 \le \text{Runway} < 12\text{ months}$: $S_{\text{fin}} = 25.0 + \left(\frac{\text{Runway} - 6.0}{6.0}\right) \times 35.0$
- $12 \le \text{Runway} < 24\text{ months}$: $S_{\text{fin}} = 60.0 + \left(\frac{\text{Runway} - 12.0}{12.0}\right) \times 30.0$
- $\text{Runway} \ge 24\text{ months}$: $S_{\text{fin}} = \min\left(100.0, 90.0 + \left(\frac{\text{Runway} - 24.0}{12.0}\right) \times 10.0\right)$

---

## Project Directory Structure

```
biOF/
├── .github/
│   └── workflows/
│       └── ci.yml                # GitHub Actions automated test & CI matrix
├── bioseeder/                    # Core application package
│   ├── __init__.py
│   ├── config.py                 # Pydantic Settings (env vars, timeouts, URLs)
│   ├── database.py               # Async SQLAlchemy engine, sessionmaker, SQLite WAL pragmas
│   ├── models/                   # SQLAlchemy 2.0 Async ORM models
│   │   ├── __init__.py
│   │   ├── company.py            # Biotech equity, exchange, valuation & financial metrics
│   │   ├── drug.py               # Drug candidate, indication, therapeutic area, TAM
│   │   ├── trial.py              # ClinicalTrials.gov study records (NCT IDs)
│   │   ├── catalyst.py           # Catalyst events (PDUFA, Phase 1/2/3, AdCom, CRL)
│   │   └── score.py              # Bio-Alpha composite score & component breakdown
│   ├── engine/                   # Quantitative scoring models
│   │   ├── __init__.py
│   │   ├── proximity.py          # Exponential catalyst time-decay calculation
│   │   ├── pos_matrix.py         # Empirical clinical transition probability benchmarks
│   │   ├── dilution.py           # Cash runway vs. secondary dilution hazard
│   │   ├── asymmetry.py          # TAM-to-market-cap ratio scoring
│   │   └── bio_alpha.py          # Composite 5-factor Bio-Alpha engine
│   ├── collectors/               # Async upstream data ingestion clients
│   │   ├── __init__.py
│   │   ├── base.py               # Rate-limiting, retry logic, exponential backoff with jitter
│   │   ├── clinicaltrials.py     # ClinicalTrials.gov API v2 study parser
│   │   ├── openfda.py            # openFDA Drugs@FDA approvals & submissions parser
│   │   └── market_data.py        # Yahoo Finance market cap, cash, & runway calculator
│   ├── api/                      # FastAPI web server and routing layer
│   │   ├── __init__.py
│   │   ├── main.py               # Application factory, lifespan, CORS, static mounts
│   │   ├── schemas.py            # Pydantic v2 request & response schemas
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── catalysts.py      # /api/v1/catalysts & /api/v1/pdufa-calendar
│   │       ├── screener.py       # /api/v1/screener (multi-variable screening)
│   │       ├── companies.py      # /api/v1/companies & /api/v1/company/{ticker}
│   │       ├── live_feed.py      # /api/v1/approvals/live (breaking news ticker)
│   │       └── seed.py           # /api/v1/seed (institutional data seeder)
│   └── static/                   # Dark Cyber-Biotech Terminal UI
│       ├── index.html            # Multi-panel Bloomberg terminal layout
│       ├── css/
│       │   ├── tokens.css        # Cyber-Biotech color variables and typography
│       │   └── terminal.css      # Table grids, countdown pills, marquee styles
│       └── js/
│           ├── app.js            # Orchestrator, KPI calculator, filter dispatcher
│           ├── calendar.js       # Catalyst table & countdown timer renderer
│           ├── ticker.js         # Live marquee news ticker manager
│           └── dossier.js        # Company modal, drug pipeline stages & trial links
├── tests/                        # Automated Pytest suite (23 async tests)
│   ├── conftest.py               # In-memory SQLite fixtures & ASGI async clients
│   ├── test_api.py               # API workflow, filtering, and auth tests
│   ├── test_collectors.py        # Ingestion schema parsing & resilience tests
│   ├── test_database.py          # Session & SQLite PRAGMA configuration tests
│   ├── test_frontend_serving.py  # Static UI root serving verification
│   ├── test_models.py            # ORM cascade and relationship tests
│   └── test_scoring_engine.py    # Math bounds, decay, PoS, and dilution tests
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusions file
├── CONTRIBUTING.md               # Open source contribution guidelines
├── LICENSE                       # MIT License
├── pyproject.toml                # Package metadata, dependencies, and pytest configuration
├── README.md                     # Project documentation
└── SECURITY.md                   # Security vulnerability reporting policy
```

---

## Prerequisites & Requirements

- **Python:** `Python >= 3.10` (tested on `Python 3.10`, `3.11`, `3.12`, `3.13`)
- **Operating System:** Linux, macOS, or Windows
- **Database:** SQLite (built-in, no installation required) or PostgreSQL (`postgresql+asyncpg://`)
- **Node.js:** **Not required** (the terminal frontend uses zero-build native ES6)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/biOF.git
cd biOF
```

### 2. Set Up a Virtual Environment

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Package and Dependencies

```bash
# Production installation
pip install -e ../ortak -e .

# Development installation (includes pytest, pytest-asyncio, pytest-cov)
pip install -e ../ortak -e ".[dev]"
```

---

## Configuration

biOF is configured via environment variables or a `.env` file in the project root. All settings are validated at runtime via `pydantic-settings`.

### Configuration Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | `str` | `"biOF"` | Application title reported in API and UI |
| `VERSION` | `str` | `"0.1.0"` | Release version |
| `API_PREFIX` | `str` | `"/api/v1"` | Base URL prefix for all REST API endpoints |
| `DEBUG` | `bool` | `True` | Enables debug mode; permits unauthenticated `/seed` requests |
| `DATABASE_URL` | `str` | `"sqlite+aiosqlite:///./bioseeder.db"` | Async SQLAlchemy connection URI (`sqlite+aiosqlite` or `postgresql+asyncpg`) |
| `DATABASE_ECHO` | `bool` | `False` | Log raw SQL statements generated by SQLAlchemy |
| `CLINICALTRIALS_BASE_URL` | `str` | `"https://clinicaltrials.gov/api/v2"` | ClinicalTrials.gov API v2 endpoint |
| `OPENFDA_BASE_URL` | `str` | `"https://api.fda.gov"` | openFDA API endpoint |
| `OPENFDA_API_KEY` | `Optional[str]` | `None` | Optional openFDA key for higher query quotas |
| `COLLECTOR_RATE_LIMIT_HZ` | `float` | `5.0` | Maximum requests per second per collector |
| `COLLECTOR_MAX_RETRIES` | `int` | `4` | Retry attempts on HTTP 429 or 5xx failures |
| `COLLECTOR_BACKOFF_BASE_SEC` | `float` | `1.0` | Base delay for exponential backoff calculations |
| `COLLECTOR_TIMEOUT_SEC` | `float` | `15.0` | Upstream HTTP client timeout in seconds |
| `ADMIN_API_KEY` | `Optional[str]` | `None` | Required in `X-Admin-Key` header for `/seed` when `DEBUG=False` |
| `CORS_ORIGINS` | `List[str]` | `["*"]` | Allowed CORS origins for API consumers |

---

## Quick Start

### 1. Launch the biOF Server

```bash
uvicorn bioseeder.api.main:app --reload --port 8000
```

### 2. Seed Initial Institutional Data

On first boot, biOF will automatically populate curated institutional benchmark data if the database is empty. You can also seed explicitly via `curl`:

```bash
curl -X POST http://localhost:8000/api/v1/seed
```

### 3. Open in Browser

- **Cyber-Biotech Terminal UI:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## REST API Reference

All API routes are prefixed with `/api/v1`.

| Method | Endpoint | Description | Query Parameters |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service and database connectivity health check | None |
| `GET` | `/api/v1/catalysts` | List upcoming and past biotech catalysts with scores | `days_ahead`, `phase`, `indication`, `min_score`, `catalyst_type`, `include_past` |
| `GET` | `/api/v1/pdufa-calendar` | Filter exclusively for PDUFA, FDA Approval, and AdCom dates | `days_ahead`, `include_past` |
| `GET` | `/api/v1/screener` | Multi-variable catalyst screener sorted by Bio-Alpha score | `min_score`, `min_runway`, `max_market_cap`, `phase`, `indication`, `dilution_risk_only`, `include_past` |
| `GET` | `/api/v1/companies` | List all tracked biopharmaceutical companies | None |
| `GET` | `/api/v1/company/{ticker}` | Deep-dive dossier for a company, its drug pipeline, and trials | None |
| `GET` | `/api/v1/approvals/live` | Real-time regulatory feed (approvals, CRLs, AdComs, trials) | None |
| `POST` | `/api/v1/seed` | Populate database with institutional biopharma data | Header `X-Admin-Key` (required if `DEBUG=False`) |

### Example API Request & Response

#### Request: Get High-Alpha Catalysts within 30 Days

```bash
curl "http://localhost:8000/api/v1/catalysts?days_ahead=30&min_score=70.0"
```

#### Response:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "ticker": "VRTX",
      "company_name": "Vertex Pharmaceuticals",
      "exchange": "NASDAQ",
      "market_cap": 118500.0,
      "cash_runway_months": 48.5,
      "drug_name": "VX-548",
      "generic_name": "Suzetrigine",
      "indication": "Moderate-to-Severe Acute Pain",
      "therapeutic_area": "Neurology / Pain",
      "phase": "NDA/BLA",
      "catalyst_type": "PDUFA",
      "target_date": "2026-10-13",
      "days_to_event": 22,
      "date_precision": "EXACT",
      "status": "UPCOMING",
      "outcome": "PENDING",
      "details": "FDA PDUFA target action date for NDA review of Suzetrigine in acute pain under Priority Review.",
      "bio_alpha_score": 79.5,
      "dilution_flag": false,
      "score_breakdown": {
        "proximity_score": 49.7,
        "pos_score": 100.0,
        "asymmetry_score": 0.9,
        "dilution_hazard_score": 100.0,
        "smart_money_score": 65.0
      }
    }
  ]
}
```

---

## Testing & Quality Assurance

biOF comes with an automated, asynchronous test suite verifying:
- Upstream collector parsing against official ClinicalTrials.gov API v2 and openFDA response schemas.
- Collector rate limiting, retry semantics, and exponential backoff on HTTP 429/5xx errors.
- Scoring engine mathematical bounds ($0 \le S \le 100$), time-decay curves, and dilution penalty thresholds.
- Full API workflow, temporal filtering (`days_ahead`, `include_past`), and production authorization guards.
- Static terminal asset serving.

### Run All Tests

```bash
pytest
```

### Run Tests with Verbose Output and Coverage Report

```bash
pytest -v --cov=bioseeder
```

Expected output:
```text
============================= test session starts =============================
collected 23 items

tests/test_api.py::test_api_endpoints_workflow PASSED                    [  4%]
tests/test_api.py::test_catalyst_temporal_filtering PASSED               [  8%]
tests/test_api.py::test_screener_excludes_null_market_cap PASSED         [ 13%]
tests/test_api.py::test_seed_authentication_in_production_mode PASSED    [ 17%]
tests/test_collectors.py::test_parse_clinical_trials_study_v2_official_schema PASSED [ 21%]
tests/test_collectors.py::test_parse_clinical_trials_study_nested_fallback PASSED [ 26%]
tests/test_collectors.py::test_parse_openfda_drug_approvals PASSED       [ 30%]
tests/test_collectors.py::test_parse_openfda_multiple_submissions_sorts_descending PASSED [ 34%]
tests/test_collectors.py::test_market_data_runway_calculation PASSED     [ 39%]
tests/test_collectors.py::test_base_collector_404_raises_immediately_without_retries PASSED [ 43%]
tests/test_collectors.py::test_base_collector_500_retries_and_raises PASSED [ 47%]
tests/test_database.py::test_database_connection PASSED                  [ 52%]
tests/test_database.py::test_session_generator PASSED                    [ 56%]
tests/test_database.py::test_sqlite_pragma_configuration PASSED          [ 60%]
tests/test_frontend_serving.py::test_terminal_root_serving PASSED        [ 65%]
tests/test_models.py::test_create_and_query_company_and_pipeline PASSED  [ 69%]
tests/test_scoring_engine.py::test_proximity_decay_curve PASSED          [ 73%]
tests/test_scoring_engine.py::test_pos_matrix PASSED                     [ 78%]
tests/test_scoring_engine.py::test_dilution_hazard PASSED                [ 82%]
tests/test_scoring_engine.py::test_proximity_past_events PASSED          [ 86%]
tests/test_scoring_engine.py::test_pos_matrix_new_benchmarks_and_matching PASSED [ 91%]
tests/test_scoring_engine.py::test_asymmetry_score PASSED                [ 95%]
tests/test_scoring_engine.py::test_composite_bio_alpha_calculation PASSED [100%]

============================= 23 passed in 5.18s ==============================
```

---

## Rasathane Telegram kanalı (Türkçe kurulum)

biOF, ABD borsalarındaki ilaç ve biyotek şirketlerinin **faz ve FDA gelişmelerini** Rasathane grubunun (`t.me/rasathane`) **biOF** konusuna kart olarak gönderir. Kanal yalnız resmi kaynakları kullanır: ClinicalTrials.gov (çalışma kaydı değişiklikleri), SEC EDGAR (8-K basın bültenleri) ve Yahoo Finance (piyasa değeri, nakit pisti). Panelin örnek verisi ve Bio-Alpha puanı kanala girmez.

| Paylaşım | Ne zaman | İçerik |
| :--- | :--- | :--- |
| Sabah Bülteni | Salı–Cumartesi, İstanbul 09:00 | Önceki ABD işlem gününün Faz 2/3 ve FDA olayları, kart başına 6 olay, her kart ayrı mesaj |
| Önümüzdeki 60 gün | Pazartesi, İstanbul 09:00 | Birincil bitişi yaklaşan Faz 2/3 çalışmalar ve nakit pisti |
| Büyük olay | ABD seansında saatte bir kontrol | Faz 3 sonucu, FDA onayı ya da ret mektubu; günde en fazla 2 mesaj |

Kartlar Rasathane'nin ortak Kâğıt düzenindedir; mesaj metni yalnız "biOF · Kart adı · GG.AA.YYYY" satırıdır. Kartlar sonucun iyi ya da kötü olduğunu yorumlamaz, her kartta "Yatırım tavsiyesi değildir" yazar. Olay yoksa hiçbir şey gönderilmez. Veri okunamazsa o paylaşım gönderilmez ve hata sahibine özel mesajla bildirilir.

### Kurulum

1. **Konu:** Rasathane grubunda (konular açık) **biOF** adlı bir konu açın ve konuya yalnız yöneticilerin yazabilmesini sağlayın.
2. **Bot:** Rasathane botunu grupta yönetici yapın (mesaj gönderme izni yeterli).
3. **Konu kimliği:** biOF konusuna herhangi bir mesaj yazın, mesaja sağ tıklayıp "Bağlantıyı kopyala" deyin. Bağlantı `https://t.me/rasathane/<konu_kimliği>/<mesaj_no>` biçimindedir; ortadaki sayı konu kimliğidir.
4. **Secret'lar ve değişkenler:** GitHub'da depo → *Settings → Secrets and variables → Actions*.
   - *Secrets* sekmesi: `TELEGRAM_BOT_TOKEN` (BotFather'ın verdiği anahtar), `TELEGRAM_SAHIP_ID` (hata mesajlarının gideceği kişisel Telegram kimliğiniz; @userinfobot'tan öğrenilir).
   - *Variables* sekmesi:
     - `TELEGRAM_HEDEF` = `@rasathane:<konu_kimliği>`. İleride ayrı bir kanala geçmek için `@kanal_adi` yazmak yeterli, kod değişmez.
     - `SEC_ILETISIM` = SEC'e bildirilecek iletişim e-postası. SEC, her istekte gerçek bir iletişim adresi ister; GitHub'ın `noreply` adresini kabul etmez ve 403 verir.
     - `RASATHANE_GONDERIM` = şimdilik **boş bırakın**. Bu değer `acik` olmadıkça her koşu kurudur, yani hiçbir şey gönderilmez.
5. **`main`'e birleştirme:** Zamanlanmış iş akışları yalnız varsayılan dalda (`main`) çalışır ve durum dosyalarını (`rasathane/veri/`) oraya commit eder. `main`'de dal koruması varsa Actions'ın push edebilmesi için *github-actions[bot]* için istisna tanımlayın.
6. **İlk kurulum:** *Actions → Rasathane → Run workflow* ile sırayla çalıştırın:
   1. `evren`: şirket listesi, ilk seferde ~30–60 dk; SEC'e saniyede en fazla 5 istek gider.
   2. `ilk-kurulum`: ClinicalTrials.gov görüntüsü. Kart üretmez.
   3. `sabah`, kuru: kartları üretir.
7. **Kuru çıktılara bakmak:** Her koşunun sayfasında *Artifacts* altında `rasathane-kartlar-…` dosyası olur; içinde PNG kartlar ve mesaj açıklaması (`.txt`) vardır. Gönderimi açmadan önce en az 3 iş günü kuru çalışmasına bakın.
8. **Gönderimi açmak:** `RASATHANE_GONDERIM` değişkenini `acik` yapın. Zamanlanmış koşular artık gönderir. Elle tetiklemede "Kuru çalıştır" kutusunu kaldırmak gerekir.
   Not: GitHub aynı anda yalnız bir koşu çalıştırır ve sırada en fazla bir koşu bekletir. Zamanlanmış bir koşu sıradayken elle tetiklerseniz, sıradaki koşu iptal edilip yerine sizinki geçer. Elle tetiklemeyi İstanbul 09:00 civarında yapmayın.
9. **Durdurmak:** `RASATHANE_GONDERIM` değişkenini silin ya da başka bir değer yazın. İş akışını tümden durdurmak için *Actions → Rasathane → Disable workflow* kullanın.

### İzlenen şirketler (evren)

Evren, SEC'te sektör kodu 2834 (ilaç) ya da 2836 (biyolojik ürün) olan ve NASDAQ/NYSE/NYSE American'da işlem gören bütün şirketlerden oluşur. Liste ayda bir yenilenir: `rasathane/veri/evren.csv`. Piyasa değeri 50 milyon $'ın altında olan ya da okunamayan şirketler kartta **MİKRO** işareti taşır.

Elle düzeltme için `rasathane/evren_ek.csv` kullanılır:

```csv
islem,ticker,ad
ekle,ABCD,
cikar,WXYZ,
esle,SGEN,"Seagen Inc."
```

- `ekle`: sektör kodu farklı olsa da şirketi izle.
- `cikar`: şirketi izleme.
- `esle`: ClinicalTrials.gov'daki sponsor adını bir borsa koduna bağla. Hangi sponsorların eşleşmediğini `rasathane/veri/eslesmeyen_sponsorlar.csv` dosyasında görebilirsiniz.

### Yerelde çalıştırma ve yedek

```bash
python -m bioseeder.rasathane sabah --kuru --tarih 2026-10-23
```

Kartlar `cikti/` klasörüne yazılır. Yahoo, GitHub Actions'tan gelen istekleri engellerse `evren` işini kendi bilgisayarınızda çalıştırın. Sonra `rasathane/veri/evren.csv` dosyasını commit edip push edin. Bunun için `SEC_ILETISIM` ortam değişkeni tanımlı olmalı.

```bash
python -m bioseeder.rasathane evren
```

Yerelde gerçek gönderim yapmayın. Asıl çalıştırıcı GitHub Actions'tır; iki yer aynı anda gönderirse kayıt dosyası çakışır.

### Bakım

ABD federal tatil listesi (SEC/EDGAR'ın kapalı olduğu günler) `bioseeder/rasathane/takvim.py` dosyasında yıl yıl tutulur, şu an 2026–2027 tanımlı. Listede olmayan bir yıla gelindiğinde iş hata verir ve sahibine bildirir. Yeni yılın tatillerini yıl bitmeden ekleyin.

---

## Troubleshooting

### 1. Database Locking (`sqlite3.OperationalError: database is locked`)
- **Cause:** SQLite concurrent writes during intensive multi-threaded collector tasks.
- **Solution:** biOF automatically configures `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=30000` on connection. If deploying in high-concurrency environments, switch to PostgreSQL by setting `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname`.

### 2. Seeding Rejected with HTTP 403 Forbidden
- **Cause:** In production environments (`DEBUG=False`), the `/api/v1/seed` endpoint is locked to prevent unauthorized database resets.
- **Solution:** Supply the configured `ADMIN_API_KEY` via the `X-Admin-Key` HTTP header:
  ```bash
  curl -X POST http://localhost:8000/api/v1/seed -H "X-Admin-Key: your_secret_admin_key"
  ```
  Alternatively, set `DEBUG=True` in your development `.env` file.

### 3. Upstream Collector Rate Limiting (HTTP 429)
- **Cause:** Exceeding openFDA or ClinicalTrials.gov public rate limits.
- **Solution:** Set `COLLECTOR_RATE_LIMIT_HZ=2.0` in `.env` to throttle requests, or provide an official openFDA API key via `OPENFDA_API_KEY`.

---

## Known Limitations

- **Scheduler Automation:** Upstream data ingestion collectors (`ClinicalTrialsCollector`, `OpenFDACollector`, `MarketDataCollector`) currently execute on API invocation and seed routines; an automated background cron daemon is scheduled for the v0.2.0 milestone.
- **Live Feed Streaming:** The `/api/v1/approvals/live` feed currently serves an in-memory buffer; WebSocket push streaming is architected but not yet wired to a live Redis pub/sub broker.
- **Multi-Exchange Coverage:** Market telemetry via `yfinance` is optimized for US primary exchanges (`NASDAQ`, `NYSE`); OTCQX, OTCQB, and European biotech listings have unverified coverage.

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, development setup, coding standards, and pull request procedures.

---

## Security

Please review our [SECURITY.md](SECURITY.md) for vulnerability disclosure guidelines and security reporting policies.

---

## License

This project is licensed under the terms of the **MIT License**. See the [LICENSE](LICENSE) file for details.
