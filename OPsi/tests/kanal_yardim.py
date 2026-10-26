"""Kanal testleri için ortak sahte zincir yardımcıları."""

import datetime

from opsi.pricer import bs_put_price
from opsi.types import RawContract

NOW = datetime.datetime(2026, 10, 23, 22, 30, tzinfo=datetime.UTC)


def kontrat(**k: object) -> RawContract:
    base: dict[str, object] = {
        "symbol": "T",
        "expiry": (NOW.date() + datetime.timedelta(days=30)).isoformat(),
        "strike": 100.0,
        "bid": 1.0,
        "ask": 1.1,
        "lastPrice": 1.05,
        "volume": 10,
        "openInterest": 100,
    }
    base.update(k)
    return base  # type: ignore[return-value]


def zincir_bs(
    vadeler: dict[int, float],
    spot: float = 100.0,
    put25_iv: float | None = None,
    sadece_atm: bool = False,
) -> list[RawContract]:
    """Her vade için 70–130 arası kullanım fiyatları, verilen IV ile BS fiyatı (dar alış/satış)."""
    out: list[RawContract] = []
    for dte, iv in vadeler.items():
        exp = (NOW.date() + datetime.timedelta(days=dte)).isoformat()
        strikes = [100.0] if sadece_atm else [70 + 2.5 * i for i in range(25)]
        for k in strikes:
            sig = put25_iv if (put25_iv is not None and k < spot * 0.97) else iv
            p = bs_put_price(spot, k, dte / 365.0, 0.045, 0.0, sig)
            if p < 0.06:
                continue
            out.append(kontrat(expiry=exp, strike=k, bid=p * 0.999, ask=p * 1.001, lastPrice=p))
    return out
