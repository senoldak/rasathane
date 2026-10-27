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
    "rs_zirve": "SPY'ye Göre Güçte Zirve",
    "dip_52": "52 Haftanın Dibi",
    "olum": "Ölüm Kesişimi",
    "sma200_asagi": "SMA 200'ün Altına Düşenler",
}
ASAGI = {"dip_52", "olum", "sma200_asagi"}


@dataclass(frozen=True)
class Olcum:
    sembol: str
    kapanis: float
    degisim: float
    dolar_hacim: float
    g1h: float | None  # 5 işlem günü
    g1a: float | None
    g3a: float | None
    gyb: float | None  # yılbaşından beri


@dataclass(frozen=True)
class Sinyal:
    tur: str
    sembol: str
    kapanis: float
    degisim: float
    seviye: float  # önceki zirve-dip / SMA 200 / hacim katı / zirveye uzaklık
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
        g1h=_getiri(c, 5),
        g1a=_getiri(c, 21),
        g3a=_getiri(c, 63),
        gyb=_yilbasi(df),
    )


def _zirve(c: np.ndarray, yon: int = 1) -> float | None:
    """Kapanış önceki 252 günün en yükseğini (yon=-1: en düşüğünü) bugün ilk kez (binde 2
    payla) aştıysa o seviye."""
    if len(c) < DONEM + 2:
        return None
    sec = np.max if yon > 0 else np.min
    seviye = float(sec(c[-1 - DONEM : -1]))
    dunku = float(sec(c[-2 - DONEM : -2]))
    if yon * (c[-1] - seviye * (1 + yon * ASIM_PAYI)) > 0 and not (
        yon * (c[-2] - dunku * (1 + yon * ASIM_PAYI)) > 0
    ):
        return seviye
    return None


def _sma(c: np.ndarray, n: int) -> np.ndarray:
    s: np.ndarray = pd.Series(c).rolling(n).mean().to_numpy()
    return s


def _sma200_kesis(c: np.ndarray, s200: np.ndarray, yon: int = 1) -> float | None:
    """Önceki 20 kapanış SMA 200'ün öbür yanındaydı, bugün bu yanında."""
    if len(c) < 200 + ALTINDA_GUN + 1:
        return None
    once_c, once_s = c[-1 - ALTINDA_GUN : -1], s200[-1 - ALTINDA_GUN : -1]
    if yon * (c[-1] - s200[-1]) > 0 and bool(np.all(yon * (once_c - once_s) < 0)):
        return float(s200[-1])
    return None


def _kesisim(s50: np.ndarray, s200: np.ndarray, yon: int = 1) -> float | None:
    if len(s200) < 202 or np.isnan(s200[-2]):
        return None
    if yon * (s50[-1] - s200[-1]) > 0 and yon * (s50[-2] - s200[-2]) <= 0:
        return float(s200[-1])
    return None


def _rs_zirve(c: np.ndarray, spy: np.ndarray | None) -> float | None:
    """ETF/SPY oranı önceki 252 günün en yükseğini bugün ilk kez aştı, fiyat ise henüz 52 hafta
    zirvesinde değil: göreli güç fiyattan önce dönüyor. Değer: fiyatın zirveye uzaklığı (oran)."""
    if spy is None or len(spy) != len(c) or len(c) < DONEM + 2 or np.any(spy[-DONEM - 2 :] <= 0):
        return None
    if _zirve(c / spy) is None:
        return None
    zirve = float(np.max(c[-1 - DONEM : -1]))
    if c[-1] >= zirve:
        return None
    return float(c[-1] / zirve - 1)


def _hacim(c: np.ndarray, v: np.ndarray) -> float | None:
    if len(v) < HACIM_GUN + 1:
        return None
    ort = float(np.nanmean(v[-1 - HACIM_GUN : -1]))
    if ort <= 0 or c[-1] / c[-2] - 1 < HACIM_EN_AZ_ARTIS:
        return None
    kat = float(v[-1] / ort)
    return kat if kat >= HACIM_KAT else None


def sinyaller(
    sembol: str, df: pd.DataFrame, olcum: Olcum, spy: pd.Series | None = None
) -> list[Sinyal]:
    c = df["Close"].to_numpy(dtype=float)
    v = df["Volume"].to_numpy(dtype=float)
    s50, s200 = _sma(c, 50), _sma(c, 200)
    spy_c = None
    if spy is not None:
        hizali = spy.reindex(df.index)
        if hizali.notna().all():
            spy_c = hizali.to_numpy(dtype=float)
    bulunan = {
        "zirve_52": _zirve(c),
        "altin": _kesisim(s50, s200),
        "sma200_yukari": _sma200_kesis(c, s200),
        "hacim": _hacim(c, v),
        "rs_zirve": _rs_zirve(c, spy_c),
        "dip_52": _zirve(c, -1),
        "olum": _kesisim(s50, s200, -1),
        "sma200_asagi": _sma200_kesis(c, s200, -1),
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
