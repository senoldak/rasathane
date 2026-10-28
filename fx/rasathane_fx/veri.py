"""Yahoo Finance'ten toplu günlük ve saatlik fiyatlar."""

import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger("fx")


def indir(semboller: list[str], donem: str = "5y", aralik: str = "1d") -> dict[str, pd.DataFrame]:
    """sembol → tablo (Close); verisi gelmeyen semboller yok."""
    try:
        tablo = yf.download(
            semboller,
            period=donem,
            interval=aralik,
            auto_adjust=True,
            group_by="ticker",
            progress=False,
        )
    except Exception as e:
        log.warning("Yahoo indirilemedi: %s", e)
        return {}
    out: dict[str, pd.DataFrame] = {}
    if tablo is None or tablo.empty:
        return out
    for s in semboller:
        if s not in tablo.columns.get_level_values(0):
            continue
        parca = tablo[s][["Close"]].dropna()
        if len(parca):
            out[s] = parca
    return out
