# src/opsi/etf/tarama.py
"""ETF ölçümleri (getiri, likidite) ve günlük sinyaller; birbirinin kopyası ETF'leri ayıklama."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

EN_AZ_DOLAR_HACIM = 1_000_000.0  # son 20 günün ortalama günlük işlem tutarı ($)
DONEM = 252
ASIM_PAYI = 0.002
ALTINDA_GUN = 20  # SMA 200 kesişiminden önce çizginin altında geçen kapanış sayısı
HACIM_KAT = 3.0
HACIM_GUN = 50
HACIM_EN_AZ_ARTIS = 0.02
KOPYA_ESIGI = 0.95  # günlük getiri korelasyonu bundan yüksekse ikinci ETF aynı tema sayılır
KOPYA_GUN = 126

TURLER: dict[str, str] = {
    "zirve_52": "52 Haftanın Zirvesi",
    "altin": "Altın Kesişim",
    "sma200_yukari": "SMA 200'ü Yukarı Kesenler",
    "hacim": "Hacim Patlaması",
}


@dataclass(frozen=True)
class Olcum:
    sembol: str
    kapanis: float
    degisim: float
    dolar_hacim: float
    g1a: float | None
    g3a: float | None
    gyb: float | None  # yılbaşından beri


@dataclass(frozen=True)
class Sinyal:
    tur: str
    sembol: str
    kapanis: float
    degisim: float
    seviye: float  # önceki zirve / SMA 200 / hacim katı
    dolar_hacim: float


def _getiri(c: np.ndarray, gun: int) -> float | None:
    if len(c) <= gun or c[-1 - gun] <= 0:
        return None
    return float(c[-1] / c[-1 - gun] - 1)


def _yilbasi(df: pd.DataFrame) -> float | None:
    yil = df.index[-1].year
    once = df["Close"][df.index.year < yil]
    if once.empty or once.iloc[-1] <= 0:
        return None
    return float(df["Close"].iloc[-1] / once.iloc[-1] - 1)


def olc(sembol: str, df: pd.DataFrame) -> Olcum | None:
    """Likit değilse ya da iki günden kısa veride None."""
    c = df["Close"].to_numpy(dtype=float)
    v = df["Volume"].to_numpy(dtype=float)
    if len(c) < 2 or c[-2] <= 0:
        return None
    dolar = float(np.nanmean(c[-20:] * v[-20:]))
    if not dolar >= EN_AZ_DOLAR_HACIM:
        return None
    return Olcum(
        sembol=sembol,
        kapanis=float(c[-1]),
        degisim=float(c[-1] / c[-2] - 1),
        dolar_hacim=dolar,
        g1a=_getiri(c, 21),
        g3a=_getiri(c, 63),
        gyb=_yilbasi(df),
    )


def _zirve(c: np.ndarray) -> float | None:
    """Kapanış önceki 252 günün en yükseğini bugün ilk kez (binde 2 payla) aştıysa o seviye."""
    if len(c) < DONEM + 2:
        return None
    seviye = float(np.max(c[-1 - DONEM : -1]))
    dunku = float(np.max(c[-2 - DONEM : -2]))
    if c[-1] > seviye * (1 + ASIM_PAYI) and not c[-2] > dunku * (1 + ASIM_PAYI):
        return seviye
    return None


def _sma(c: np.ndarray, n: int) -> np.ndarray:
    s: np.ndarray = pd.Series(c).rolling(n).mean().to_numpy()
    return s


def _sma200_yukari(c: np.ndarray, s200: np.ndarray) -> float | None:
    if len(c) < 200 + ALTINDA_GUN + 1:
        return None
    once_c, once_s = c[-1 - ALTINDA_GUN : -1], s200[-1 - ALTINDA_GUN : -1]
    if c[-1] > s200[-1] and bool(np.all(once_c < once_s)):
        return float(s200[-1])
    return None


def _altin(s50: np.ndarray, s200: np.ndarray) -> float | None:
    if len(s200) < 202 or np.isnan(s200[-2]):
        return None
    if s50[-1] > s200[-1] and s50[-2] <= s200[-2]:
        return float(s200[-1])
    return None


def _hacim(c: np.ndarray, v: np.ndarray) -> float | None:
    if len(v) < HACIM_GUN + 1:
        return None
    ort = float(np.nanmean(v[-1 - HACIM_GUN : -1]))
    if ort <= 0 or c[-1] / c[-2] - 1 < HACIM_EN_AZ_ARTIS:
        return None
    kat = float(v[-1] / ort)
    return kat if kat >= HACIM_KAT else None


def sinyaller(sembol: str, df: pd.DataFrame, olcum: Olcum) -> list[Sinyal]:
    c = df["Close"].to_numpy(dtype=float)
    v = df["Volume"].to_numpy(dtype=float)
    s200 = _sma(c, 200)
    bulunan = {
        "zirve_52": _zirve(c),
        "altin": _altin(_sma(c, 50), s200),
        "sma200_yukari": _sma200_yukari(c, s200),
        "hacim": _hacim(c, v),
    }
    return [
        Sinyal(tur, sembol, olcum.kapanis, olcum.degisim, seviye, olcum.dolar_hacim)
        for tur, seviye in bulunan.items()
        if seviye is not None
    ]


def kopyalari_ayikla(sirali: list[str], veri: dict[str, pd.DataFrame]) -> list[str]:
    """Sırayı koruyarak, öndekilerden biriyle getirisi KOPYA_ESIGI üstünde örtüşen ETF'leri atar.

    Aynı endeksi izleyen fonlar (SPY, IVV, VOO) aynı gün aynı sinyali verir; tema bir kez görünür.
    """
    if len(sirali) < 2:
        return list(sirali)
    getiri = pd.DataFrame(
        {s: veri[s]["Close"].iloc[-KOPYA_GUN - 1 :].pct_change() for s in sirali}
    ).corr(min_periods=40)
    kalan: list[str] = []
    for s in sirali:
        if all(not (getiri.at[s, k] > KOPYA_ESIGI) for k in kalan):
            kalan.append(s)
    return kalan
