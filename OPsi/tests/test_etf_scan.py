# tests/test_etf_scan.py
import sqlite3

from opsi.logging import ScanAdapter, get_scan_logger
from opsi.scan import _earnings_days_cached, load_universe


def test_etf_bypasses_earnings_check(tmp_path):
    db_file = str(tmp_path / "test.db")
    con = sqlite3.connect(db_file)
    logger = ScanAdapter(get_scan_logger(1), 1)

    # For SPY (ETF), earnings should immediately return None without querying yfinance
    res = _earnings_days_cached(con, db_file, "SPY", 500.0, logger)
    assert res is None


def test_load_universe_with_etfs(monkeypatch):
    monkeypatch.setattr("opsi.fetch.get_sp500_symbols", lambda: ["AAPL", "MSFT"])

    # default universe
    all_syms = load_universe("data/opsi.db", universe="all")
    assert "SPY" in all_syms
    assert "AAPL" in all_syms

    etfs = load_universe("data/opsi.db", universe="etfs")
    assert "SPY" in etfs
    assert "AAPL" not in etfs

    stocks = load_universe("data/opsi.db", universe="stocks")
    assert stocks == ["AAPL", "MSFT"]
