# src/opsi/etf/ag.py
"""Yahoo'dan ETF başına ek veri: yakın vadeli opsiyon zinciri, en büyük hisseler, toplam varlık.

Her işlev hata verirse boş döner; bir ETF'nin eksiği koşuyu durdurmaz.
"""

import datetime
import logging
import time
from collections.abc import Callable
from functools import partial
from typing import Any, TypeVar

import pandas as pd
import yfinance as yf

from ..fetch import _throttle

VADE_GUN = 45
VADE_EN_YAKIN = 2  # bugün ve yarın biten vadeler hacmi şişirir (0DTE), sayılmaz
VADE_SAYISI = 3
# İstekler sırayla gider: GitHub sunucularında paralel istekler Yahoo oturumunu (crumb) bozuyor.

_DENEME = 4
_BEKLEME = 30.0  # hız sınırında ilk bekleme (sn); her denemede iki katı

log = logging.getLogger("opsi.etf")
T = TypeVar("T")


def _sinirli(is_: Callable[[], T], uyku: Callable[[float], None] = time.sleep) -> T:
    """Yahoo "Too Many Requests" dönerse bekleyip yeniden dener; öteki hatalar olduğu gibi çıkar."""
    for deneme in range(_DENEME):
        try:
            return is_()
        except Exception as e:
            if "Rate limit" not in str(e) and "Too Many Requests" not in str(e):
                raise
            if deneme + 1 == _DENEME:
                raise
            uyku(_BEKLEME * 2**deneme)
    raise AssertionError("ulaşılmaz")


def opsiyon_zinciri(sembol: str, bugun: datetime.date) -> pd.DataFrame:
    """45 güne kadar ilk 3 vadenin çağrı ve put'ları: tur, strike, vade, volume, openInterest."""
    try:
        t = yf.Ticker(sembol)
        vadeler = [
            v
            for v in _sinirli(lambda: t.options)
            if VADE_EN_YAKIN <= (datetime.date.fromisoformat(v) - bugun).days <= VADE_GUN
        ][:VADE_SAYISI]
        parcalar = []
        for v in vadeler:
            _throttle()
            z = _sinirli(partial(t.option_chain, v))
            for tur, df in (("C", z.calls), ("P", z.puts)):
                d = df[["strike", "volume", "openInterest"]].copy()
                d["tur"], d["vade"] = tur, v
                parcalar.append(d)
        return pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame()
    except Exception as e:
        log.warning("%s opsiyon zinciri alınamadı: %s", sembol, e)
        return pd.DataFrame()


def zincirler(semboller: list[str], bugun: datetime.date) -> dict[str, pd.DataFrame]:
    out = {}
    for s in semboller:
        _throttle()
        out[s] = opsiyon_zinciri(s, bugun)
    log.info("opsiyon zinciri: %d / %d ETF", sum(not z.empty for z in out.values()), len(out))
    return out


def ilk_hisseler(sembol: str) -> list[tuple[str, str, float]]:
    """En büyük 10 hisse: (sembol, ad, ağırlık oranı)."""
    try:
        th = _sinirli(lambda: yf.Ticker(sembol).funds_data.top_holdings)
        return [(str(i), str(r["Name"]), float(r["Holding Percent"])) for i, r in th.iterrows()]
    except Exception as e:
        log.warning("%s hisseleri alınamadı: %s", sembol, e)
        return []


def _varlik(sembol: str) -> float | None:
    try:
        bilgi: dict[str, Any] = _sinirli(lambda: yf.Ticker(sembol).info)
        v = bilgi.get("totalAssets")
        return float(v) if v else None
    except Exception:
        return None


def varliklar(semboller: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in semboller:
        _throttle()
        v = _varlik(s)
        if v is not None:
            out[s] = v
    log.info("toplam varlık: %d / %d ETF", len(out), len(semboller))
    return out
