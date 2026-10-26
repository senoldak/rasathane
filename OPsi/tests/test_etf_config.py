# tests/test_etf_config.py
from opsi import config
from opsi.fetch import get_symbols, is_etf


def test_major_etfs_defined():
    assert isinstance(config.MAJOR_ETFS, list)
    assert "SPY" in config.MAJOR_ETFS
    assert "QQQ" in config.MAJOR_ETFS
    assert "IWM" in config.MAJOR_ETFS


def test_is_etf():
    assert is_etf("SPY") is True
    assert is_etf("spy") is True
    assert is_etf("AAPL") is False


def test_get_symbols_filtering(monkeypatch):
    monkeypatch.setattr("opsi.fetch.get_sp500_symbols", lambda: ["AAPL", "MSFT"])

    etfs = get_symbols("etfs")
    assert "SPY" in etfs
    assert "AAPL" not in etfs

    stocks = get_symbols("stocks")
    assert stocks == ["AAPL", "MSFT"]

    all_syms = get_symbols("all")
    assert "AAPL" in all_syms
    assert "SPY" in all_syms
