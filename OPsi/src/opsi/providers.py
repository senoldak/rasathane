"""Quote providers: Yahoo default, Alpaca skeleton."""

from typing import Protocol

from . import fetch as _fetch
from .types import RawContract


class NotConfigured(Exception):
    pass


class QuoteProvider(Protocol):
    def get_price(self, symbol: str) -> float | None: ...
    def get_chain(self, symbol: str, right: str = "P") -> list[RawContract]: ...
    def get_history(self, symbol: str, period: str = "1y") -> list[tuple[str, float]]: ...
    def get_earnings_days(self, symbol: str) -> int | None: ...
    def get_atm_put_sample(self, symbol: str, price: float) -> dict[str, float]: ...


class YahooProvider:
    def get_price(self, symbol: str) -> float | None:
        return _fetch.get_price(symbol)

    def get_chain(self, symbol: str, right: str = "P") -> list[RawContract]:
        return _fetch.get_chain(symbol, right)

    def get_history(self, symbol: str, period: str = "1y") -> list[tuple[str, float]]:
        return _fetch.get_history(symbol, period)

    def get_earnings_days(self, symbol: str) -> int | None:
        return _fetch.get_earnings_days(symbol)

    def get_atm_put_sample(self, symbol: str, price: float) -> dict[str, float]:
        return _fetch.get_atm_put_sample(symbol, price)


class AlpacaProvider:
    def __init__(self, api_key: str | None = None) -> None:
        if not api_key:
            raise NotConfigured("No Alpaca API key; using YAHOO provider")
        self._key = api_key

    def get_price(self, symbol: str) -> float | None:
        raise NotImplementedError("Alpaca integration is a separate phase")

    def get_chain(self, symbol: str, right: str = "P") -> list[RawContract]:
        raise NotImplementedError("Alpaca integration is a separate phase")

    def get_history(self, symbol: str, period: str = "1y") -> list[tuple[str, float]]:
        raise NotImplementedError("Alpaca integration is a separate phase")

    def get_earnings_days(self, symbol: str) -> int | None:
        raise NotImplementedError("Alpaca integration is a separate phase")

    def get_atm_put_sample(self, symbol: str, price: float) -> dict[str, float]:
        raise NotImplementedError("Alpaca integration is a separate phase")


def get_default() -> QuoteProvider:
    return YahooProvider()
