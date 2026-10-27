# src/opsi/etf/ag.py
"""Yahoo'dan ETF başına ek veri: yakın vadeli opsiyon zinciri, en büyük hisseler, toplam varlık.

Her işlev hata verirse boş döner; bir ETF'nin eksiği koşuyu durdurmaz.
"""

import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pandas as pd
import yfinance as yf

VADE_GUN = 45
VADE_SAYISI = 3
_ISCI = 4  # Yahoo 8 eşzamanlı istekte hız sınırına takılıyor

log = logging.getLogger("opsi.etf")


def opsiyon_zinciri(sembol: str, bugun: datetime.date) -> pd.DataFrame:
    """45 güne kadar ilk 3 vadenin çağrı ve put'ları: tur, strike, vade, volume, openInterest."""
    try:
        t = yf.Ticker(sembol)
        vadeler = [
            v for v in t.options if (datetime.date.fromisoformat(v) - bugun).days <= VADE_GUN
        ][:VADE_SAYISI]
        parcalar = []
        for v in vadeler:
            z = t.option_chain(v)
            for tur, df in (("C", z.calls), ("P", z.puts)):
                d = df[["strike", "volume", "openInterest"]].copy()
                d["tur"], d["vade"] = tur, v
                parcalar.append(d)
        return pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame()
    except Exception as e:
        log.warning("%s opsiyon zinciri alınamadı: %s", sembol, e)
        return pd.DataFrame()


def zincirler(semboller: list[str], bugun: datetime.date) -> dict[str, pd.DataFrame]:
    with ThreadPoolExecutor(_ISCI) as h:
        return dict(zip(semboller, h.map(lambda s: opsiyon_zinciri(s, bugun), semboller)))


def ilk_hisseler(sembol: str) -> list[tuple[str, str, float]]:
    """En büyük 10 hisse: (sembol, ad, ağırlık oranı)."""
    try:
        th = yf.Ticker(sembol).funds_data.top_holdings
        return [(str(i), str(r["Name"]), float(r["Holding Percent"])) for i, r in th.iterrows()]
    except Exception as e:
        log.warning("%s hisseleri alınamadı: %s", sembol, e)
        return []


def _varlik(sembol: str) -> float | None:
    try:
        bilgi: dict[str, Any] = yf.Ticker(sembol).info
        v = bilgi.get("totalAssets")
        return float(v) if v else None
    except Exception:
        return None


def varliklar(semboller: list[str]) -> dict[str, float]:
    with ThreadPoolExecutor(_ISCI) as h:
        sonuc = dict(zip(semboller, h.map(_varlik, semboller)))
    return {s: v for s, v in sonuc.items() if v is not None}
