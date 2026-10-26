# src/opsi/kanal/evren.py
"""Kanalın taradığı sabit evren: opsiyonu en likit ~185 ABD hissesi ve ETF.

Liste `kanal_veri/evren.csv`'de durur; `evren_yenile()` ağdan yeniden üretir (elle, ara sıra).
"""

import csv
from pathlib import Path
from typing import TypedDict

import yfinance as yf

from .. import config, fetch

EVREN_YOLU = Path("kanal_veri/evren.csv")
_MIN_FIYAT = 2.0


class EvrenSatiri(TypedDict):
    sembol: str
    ad: str
    etf: bool


def evren_oku(yol: Path = EVREN_YOLU) -> list[EvrenSatiri]:
    with yol.open(newline="", encoding="utf-8") as f:
        return [
            {"sembol": r["sembol"], "ad": r["ad"], "etf": r["etf"] == "1"}
            for r in csv.DictReader(f)
        ]


def evren_sec(adaylar: dict[str, tuple[float, int]], adet: int = 185) -> list[str]:
    """{sembol: (fiyat, en yakın vade toplam put OI)} → fiyatı ≥ $2 olanlardan OI'si en yüksekler."""
    uygun = [(s, oi) for s, (fiyat, oi) in adaylar.items() if fiyat >= _MIN_FIYAT]
    uygun.sort(key=lambda x: (-x[1], x[0]))
    return [s for s, _ in uygun[:adet]]


def _yakin_vade_put_oi(sembol: str) -> int:
    fetch._throttle()
    try:
        t = yf.Ticker(sembol)
        vadeler = t.options or []
        if not vadeler:
            return 0
        puts = t.option_chain(vadeler[0]).puts
        return int(sum(fetch._to_int(v) for v in puts["openInterest"]))
    except Exception:
        return 0


def _ad(sembol: str) -> str:
    fetch._throttle()
    try:
        info = yf.Ticker(sembol).info or {}
        return str(info.get("shortName") or info.get("longName") or sembol)
    except Exception:
        return sembol


def evren_yenile(yol: Path = EVREN_YOLU) -> int:
    """S&P 500 ∪ Nasdaq-100 ∪ büyük ETF'leri ölçer, en likitleri yazar; satır sayısını döner."""
    adaylar_s = sorted(
        set(fetch.get_universe_symbols("sp500"))
        | set(fetch.get_universe_symbols("nasdaq100"))
        | set(config.MAJOR_ETFS)
    )
    adaylar: dict[str, tuple[float, int]] = {}
    for s in adaylar_s:
        fiyat = fetch.get_price(s)
        if fiyat is None or fiyat < _MIN_FIYAT:
            continue
        adaylar[s] = (fiyat, _yakin_vade_put_oi(s))
    secilen = evren_sec(adaylar)
    yol.parent.mkdir(parents=True, exist_ok=True)
    with yol.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sembol", "ad", "etf"])
        for s in sorted(secilen):
            w.writerow([s, _ad(s), "1" if fetch.is_etf(s) else "0"])
    return len(secilen)
