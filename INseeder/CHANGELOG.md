# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-09-20

### Added
- **SEC EDGAR Ingestion:** Automated async polling of SEC Form 4 Atom feeds and XML filings with Fair Access throttling and custom User-Agent headers.
- **Conviction Scoring Model (0–100):** Weighted multi-factor model evaluating insider seniority (CEO, CFO, Director, 10% Owner), transaction dollar value, holding increase %, 7-day cluster buying, and Rule 10b5-1 plan detection.
- **Dynamic Rule Engine:** Real-time trade matching based on user-configured criteria (minimum score, minimum dollar volume, allowed roles, allowed transaction codes, auto-execution toggle).
- **Multi-Channel Alerting:** Instant notifications to Telegram Bot API and Discord Webhooks with formatted trade cards and direct links to SEC filings.
- **Brokerage Adapters:**
  - `PaperBroker`: Zero-risk simulation engine with $100,000 virtual cash and PnL tracking.
  - `AlpacaBroker`: REST API adapter for Alpaca Markets Paper and Live accounts.
  - `IBKRBroker`: Gateway adapter for Interactive Brokers Client Portal API.
- **FastAPI Backend:** REST API exposing trade history, signal feed, rule CRUD, portfolio tracking, manual order execution, Hyperliquid market cross-referencing (`/api/hyperliquid/markets`), and Server-Sent Events (SSE) streaming.
- **Web Terminal:** Responsive dark-mode dashboard built with Vanilla HTML5/CSS3/JavaScript featuring live ticker stream, high-conviction signals, rule builder, paper portfolio view, and the Hyperliquid Insider Alpha Radar.
- **Historic Backfill CLI:** Standalone CLI tool (`scripts/backfill.py`) to download and parse historical SEC Form 4 filings from daily indices across configurable date ranges.
- **Test Suite:** 36 unit and integration tests with 100% pass rate across all core modules, brokers, parsers, and API endpoints.
- **Open-Source Infrastructure:** Comprehensive `README.md`, MIT License, contribution guide, security policy, code of conduct, and GitHub Actions CI workflow.
