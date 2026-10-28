"""Kur ölçümleri ve günlük sinyaller: sert hareket, 52 hafta zirve/dip, oynaklık rejimi."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .evren import ADLAR, EURTRY, SEPET, USDTRY

DONEM = 252
_OYNAKLIK_GUN = 60
BUYUK_Z = 2.5  # günlük getiri / 60 günlük std
BUYUK_EN_AZ = 0.0075  # ve en az %0,75 (kurlar emtiadan sakin)
SUPHELI_Z = 8.0  # bunun üstü çoğu zaman Yahoo'nun hatalı kotasyonu: sinyal verilmez
OYN_GUN = 21
OYN_UC = 0.95  # 1 aylık oynaklık son 5 yılın üst %5'inde
YILLIK = float(np.sqrt(252))
SIVRI = 0.05

TURLER = {
    "yukselis": "Sert Yükseliş",
    "dusus": "Sert Düşüş",
    "zirve_52": "52 Hafta Zirvesi",
    "dip_52": "52 Hafta Dibi",
    "oynaklik": "Oynaklık Sıçraması",
}
YON = {"yukselis": 1, "zirve_52": 1, "dusus": -1, "dip_52": -1}


@dataclass(frozen=True)
class Olcum:
    sembol: str
    kapanis: float
    gunluk: float
    g1h: float | None
    g1a: float | None
    gyb: float | None
    z: float | None


@dataclass(frozen=True)
class Sinyal:
    tur: str
    sembol: str
    kapanis: float
    gunluk: float
    seviye: float  # yukselis/dusus: z; zirve/dip: önceki 52 hafta seviyesi; oynaklik: yıllık oyn.


def kapanis(df: pd.DataFrame) -> pd.Series:
    c = df["Close"].astype(float).dropna()
    c.index = pd.DatetimeIndex(c.index).tz_localize(None).normalize()
    c = c[~c.index.duplicated(keep="last")]
    # Yahoo'nun tek günlük hatalı kotasyonları: komşularından %5 sapıp geri dönen noktalar atılır
    once, sonra = c.shift(1), c.shift(-1)
    sivri = ((c / once - 1).abs() > SIVRI) & ((sonra / once - 1).abs() < SIVRI / 5)
    return c[~sivri]


def getiri(c: pd.Series, gun: int) -> float | None:
    return float(c.iloc[-1] / c.iloc[-1 - gun] - 1) if len(c) > gun else None


def olc(sembol: str, df: pd.DataFrame) -> Olcum | None:
    c = kapanis(df)
    if len(c) < 2:
        return None
    r = c.pct_change().dropna()
    std = float(r.iloc[-1 - _OYNAKLIK_GUN : -1].std()) if len(r) > _OYNAKLIK_GUN else None
    gunler = pd.DatetimeIndex(c.index)
    once = c[gunler.year < gunler[-1].year]
    return Olcum(
        sembol=sembol,
        kapanis=float(c.iloc[-1]),
        gunluk=float(r.iloc[-1]),
        g1h=getiri(c, 5),
        g1a=getiri(c, 21),
        gyb=float(c.iloc[-1] / once.iloc[-1] - 1) if len(once) else None,
        z=float(r.iloc[-1] / std) if std else None,
    )


def oynaklik_serisi(c: pd.Series, gun: int = OYN_GUN) -> pd.Series:
    """Yıllıklaştırılmış gerçekleşen oynaklık (günlük log getirilerin kayan std'si)."""
    oyn: pd.Series = (c.apply(np.log).diff().rolling(gun).std() * YILLIK).dropna()
    return oyn


def yuzdelik(s: pd.Series) -> float:
    """Son değerin altında kalan geçmiş günlerin payı."""
    return float((s.iloc[:-1] < s.iloc[-1]).mean()) if len(s) > 1 else 0.5


def sinyaller(sembol: str, df: pd.DataFrame, o: Olcum) -> list[Sinyal]:
    out: list[Sinyal] = []
    if o.z is not None and abs(o.z) >= SUPHELI_Z:
        return []
    if o.z is not None and abs(o.z) >= BUYUK_Z and abs(o.gunluk) >= BUYUK_EN_AZ:
        tur = "yukselis" if o.gunluk > 0 else "dusus"
        out.append(Sinyal(tur, sembol, o.kapanis, o.gunluk, o.z))
    c = kapanis(df)
    if len(c) > DONEM:
        onceki = c.iloc[-1 - DONEM : -1]
        ust, alt = float(onceki.max()), float(onceki.min())
        if o.kapanis > ust:
            out.append(Sinyal("zirve_52", sembol, o.kapanis, o.gunluk, ust))
        elif o.kapanis < alt:
            out.append(Sinyal("dip_52", sembol, o.kapanis, o.gunluk, alt))
    oy = oynaklik_serisi(c)
    if len(oy) > DONEM and yuzdelik(oy) >= OYN_UC and yuzdelik(oy.iloc[:-1]) < OYN_UC:
        out.append(Sinyal("oynaklik", sembol, o.kapanis, o.gunluk, float(oy.iloc[-1])))
    return out


def sepet(tablolar: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    """TL sepeti: (USD/TRY + EUR/TRY) / 2, iki serinin ortak günlerinde."""
    if USDTRY not in tablolar or EURTRY not in tablolar:
        return None
    s = ((kapanis(tablolar[USDTRY]) + kapanis(tablolar[EURTRY])) / 2).dropna()
    return pd.DataFrame({"Close": s}) if len(s) else None


def ad(sembol: str) -> str:
    if sembol == SEPET:
        return "TL sepeti"
    return ADLAR[sembol].ad if sembol in ADLAR else sembol
