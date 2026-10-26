# tests/test_providers.py
import pytest

from opsi import providers


def test_default_is_yahoo():
    assert isinstance(providers.get_default(), providers.YahooProvider)


def test_yahoo_delegates(monkeypatch):
    from opsi import fetch

    monkeypatch.setattr(fetch, "get_price", lambda s: 20.0)
    assert providers.YahooProvider().get_price("AAA") == 20.0


def test_alpaca_without_key():
    with pytest.raises(providers.NotConfigured):
        providers.AlpacaProvider(api_key=None).get_price("AAA")
