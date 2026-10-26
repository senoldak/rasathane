import asyncio
from typing import Any, Dict, Optional
import yfinance as yf


class MarketDataCollector:
    """Market and financial data collector using Yahoo Finance."""

    async def fetch_ticker_overview_async(self, ticker: str) -> Dict[str, Any]:
        """Asynchronously fetch market overview by running synchronous yfinance in thread pool."""
        return await asyncio.to_thread(self.fetch_ticker_overview, ticker)

    def calculate_cash_runway(self, cash_m: float, quarterly_burn_m: float) -> float:
        """
        Calculate estimated cash runway in months:
        Runway = Cash / (Quarterly Burn / 3)
        """
        if quarterly_burn_m <= 0:
            # Company is cash-flow positive or breaking even
            return 999.0

        monthly_burn = quarterly_burn_m / 3.0
        if monthly_burn <= 0:
            return 999.0

        runway = cash_m / monthly_burn
        return round(runway, 1)

    def fetch_ticker_overview(self, ticker: str) -> Dict[str, Any]:
        """Fetch market cap, cash, burn rate, and float for a ticker."""
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}

            # Market cap in $M
            raw_market_cap = info.get("marketCap")
            market_cap_m = round(raw_market_cap / 1_000_000, 2) if raw_market_cap else None

            # Enterprise value in $M
            raw_ev = info.get("enterpriseValue")
            ev_m = round(raw_ev / 1_000_000, 2) if raw_ev else None

            # Cash and cash equivalents in $M
            raw_cash = info.get("totalCash")
            cash_m = round(raw_cash / 1_000_000, 2) if raw_cash else None

            # Operating cash flow in $M (estimate quarterly burn)
            raw_ocf = info.get("operatingCashflow")
            quarterly_burn_m = None
            if raw_ocf is not None:
                # If operating cash flow is negative, burn rate is positive outflow
                quarterly_burn_m = round(abs(raw_ocf / 4_000_000), 2) if raw_ocf < 0 else 0.0

            runway = None
            if cash_m is not None and quarterly_burn_m is not None:
                runway = self.calculate_cash_runway(cash_m, quarterly_burn_m)

            float_shares = info.get("floatShares")
            float_m = round(float_shares / 1_000_000, 2) if float_shares else None

            short_pct = info.get("shortPercentOfFloat")
            short_interest_pct = round(short_pct * 100, 2) if short_pct else None

            return {
                "ticker": ticker.upper(),
                "name": info.get("shortName") or info.get("longName") or ticker,
                "exchange": info.get("exchange", "NASDAQ"),
                "market_cap": market_cap_m,
                "enterprise_value": ev_m,
                "cash_and_equivalents": cash_m,
                "quarterly_burn_rate": quarterly_burn_m,
                "cash_runway_months": runway,
                "float_shares": float_m,
                "short_interest_pct": short_interest_pct,
            }
        except Exception as exc:
            return {
                "ticker": ticker.upper(),
                "error": str(exc),
            }
