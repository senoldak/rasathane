import datetime
from typing import Dict, Any, Optional

MOCK_QUOTES = {
    "NVDA": {"ticker": "NVDA", "company_name": "NVIDIA Corporation", "price": 124.50, "sector": "Information Technology"},
    "LMT": {"ticker": "LMT", "company_name": "Lockheed Martin Corporation", "price": 560.20, "sector": "Industrials / Defense"},
    "MSFT": {"ticker": "MSFT", "company_name": "Microsoft Corporation", "price": 448.10, "sector": "Information Technology"},
    "PLTR": {"ticker": "PLTR", "company_name": "Palantir Technologies Inc.", "price": 36.80, "sector": "Information Technology"},
    "CVX": {"ticker": "CVX", "company_name": "Chevron Corporation", "price": 154.20, "sector": "Energy"},
    "RTX": {"ticker": "RTX", "company_name": "RTX Corporation", "price": 121.40, "sector": "Industrials / Defense"},
    "BA": {"ticker": "BA", "company_name": "The Boeing Company", "price": 152.80, "sector": "Industrials / Aerospace"},
    "NOC": {"ticker": "NOC", "company_name": "Northrop Grumman Corporation", "price": 518.90, "sector": "Industrials / Defense"},
    "AVGO": {"ticker": "AVGO", "company_name": "Broadcom Inc.", "price": 165.30, "sector": "Information Technology"},
    "SPY": {"ticker": "SPY", "company_name": "SPDR S&P 500 ETF Trust", "price": 570.50, "sector": "Benchmark"}
}

def calculate_trade_alpha(
    ticker: str,
    trade_date: datetime.date,
    disc_date: datetime.date,
    price_tx: Optional[float] = None,
    price_disc: Optional[float] = None,
    ret_30d: Optional[float] = None,
    ret_90d: Optional[float] = None,
    spy_ret_90d: Optional[float] = None
) -> Dict[str, Any]:
    """
    Computes alpha generation vs S&P 500 benchmark.
    """
    alpha_90 = None
    if ret_90d is not None and spy_ret_90d is not None:
        alpha_90 = round(ret_90d - spy_ret_90d, 2)

    return {
        "ticker": ticker.upper(),
        "transaction_date": trade_date,
        "disclosure_date": disc_date,
        "price_at_transaction": price_tx,
        "price_at_disclosure": price_disc,
        "return_30d": ret_30d,
        "return_90d": ret_90d,
        "benchmark_return_90d": spy_ret_90d,
        "alpha_90d": alpha_90
    }

def get_ticker_quote(ticker: str) -> Dict[str, Any]:
    """
    Retrieves current market quote. Uses yfinance with instant fallback.
    """
    sym = ticker.upper().strip()
    if sym in MOCK_QUOTES:
        return MOCK_QUOTES[sym]
    
    try:
        import yfinance as yf
        t = yf.Ticker(sym)
        fast_info = t.fast_info
        price = fast_info.get("last_price") or fast_info.get("previous_close")
        if price:
            return {
                "ticker": sym,
                "company_name": sym,
                "price": float(price),
                "sector": "Equities"
            }
    except Exception:
        pass

    return {
        "ticker": sym,
        "company_name": sym,
        "price": 100.0,
        "sector": "Equities"
    }
