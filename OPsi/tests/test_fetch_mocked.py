# tests/test_fetch_mocked.py
"""Ağ gerektirmeyen fetch testleri: yfinance/pandas mock'lanır."""

import datetime
from typing import ClassVar

import pandas as pd

from opsi import fetch


class _FakePuts:
    _ROWS: ClassVar[list[dict[str, object]]] = [
        {
            "strike": 13.0,
            "bid": 0.0,
            "ask": 0.0,
            "lastPrice": 0.08,
            "volume": 100,
            "openInterest": 500,
        },
        {
            "strike": 14.0,
            "bid": 0.07,
            "ask": 0.09,
            "lastPrice": float("nan"),
            "volume": 50,
            "openInterest": 200,
        },
        {
            "strike": 15.0,
            "bid": 0.05,
            "ask": 0.07,
            "lastPrice": 0.06,
            "volume": float("nan"),
            "openInterest": float("nan"),
        },
    ]

    def iterrows(self):
        yield from enumerate(self._ROWS)


class _FakeChain:
    puts = _FakePuts()


class _FakeTicker:
    def __init__(self, *a, **k):
        pass

    options: ClassVar[list[str]] = [
        (datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=10)).isoformat(),
        "2030-01-01",
        "bad-expiry",
    ]

    def option_chain(self, exp):
        if exp == "2030-01-01":
            raise RuntimeError("boom")
        if exp == "bad-expiry":
            raise RuntimeError("boom")
        return _FakeChain()

    def history(self, period="1d"):
        return pd.DataFrame({"Close": [14.56]})


def test_sp500_symbols_mocked(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda url: pd.DataFrame({"Symbol": [" F ", "BAC"]}))
    assert fetch.get_sp500_symbols() == ["BAC", "F"]


def test_get_price_ok_and_empty(monkeypatch):
    monkeypatch.setattr(fetch, "yf", _FakeModule())
    assert fetch.get_price("F") == 14.56


def test_get_price_empty_history(monkeypatch):
    class T(_FakeTicker):
        def history(self, period="1d"):
            return pd.DataFrame()

    monkeypatch.setattr(fetch.yf, "Ticker", T)
    assert fetch.get_price("F") is None


def test_get_price_exception(monkeypatch):
    def boom(symbol):
        raise RuntimeError("down")

    monkeypatch.setattr(fetch.yf, "Ticker", boom)
    assert fetch.get_price("F") is None


def test_raw_chain_nan_and_bad_expiry(monkeypatch):
    monkeypatch.setattr(fetch.yf, "Ticker", _FakeTicker)
    out = fetch._raw_chain("F")
    assert len(out) == 3
    assert out[0]["lastPrice"] == 0.08
    assert out[1]["lastPrice"] == 0.0  # NaN sanitize
    assert out[2]["volume"] == 0 and out[2]["openInterest"] == 0  # NaN sanitize
    chains = fetch.get_put_chain("F", max_dte_min=0, max_dte_max=5000)
    assert {c["strike"] for c in chains} == {13.0, 14.0, 15.0}


class _FakeModule:
    Ticker = _FakeTicker


def test_earnings_days_dict_calendar(monkeypatch):
    """yfinance 1.x: Ticker.calendar bir sözlük döndürür."""
    hedef = datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=5)

    class T(_FakeTicker):
        calendar: ClassVar[dict[str, object]] = {"Earnings Date": [hedef]}

    monkeypatch.setattr(fetch.yf, "Ticker", T)
    assert fetch.get_earnings_days("F") == 5
