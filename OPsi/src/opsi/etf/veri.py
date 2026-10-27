# src/opsi/etf/veri.py
"""Yahoo Finance'ten toplu günlük OHLCV (bölük bölük yf.download)."""

import logging
import time

import pandas as pd
import yfinance as yf

BOLUK = 200
_ARA = 1.0
_SUTUNLAR = ["Close", "High", "Low", "Volume"]

log = logging.getLogger("opsi.etf")


def _ayir(tablo: pd.DataFrame, semboller: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if tablo is None or tablo.empty:
        return out
    for s in semboller:
        if isinstance(tablo.columns, pd.MultiIndex):
            if s not in tablo.columns.get_level_values(0):
                continue
            parca = tablo[s]
        elif len(semboller) == 1:
            parca = tablo
        else:
            continue
        if not set(_SUTUNLAR) <= set(parca.columns):
            continue
        parca = parca[_SUTUNLAR].dropna(subset=["Close"])
        if len(parca):
            out[s] = parca
    return out


def indir(semboller: list[str], donem: str = "2y") -> dict[str, pd.DataFrame]:
    """sembol → günlük tablo (Close, High, Low, Volume); verisi gelmeyen semboller yok."""
    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(semboller), BOLUK):
        bolum = semboller[i : i + BOLUK]
        try:
            tablo = yf.download(
                bolum,
                period=donem,
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as e:
            log.warning("%d. bölük indirilemedi: %s", i // BOLUK + 1, e)
            continue
        out.update(_ayir(tablo, bolum))
        time.sleep(_ARA)
    return out
