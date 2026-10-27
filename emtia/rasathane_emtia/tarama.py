"""Fiyat ölçümleri ve sinyaller: büyük günlük hareket, 52 hafta zirve/dip, oranlarda uç, gram altın."""

from dataclasses import dataclass

import pandas as pd

from .evren import ONS_GRAM, ORANLAR, Oran

DONEM = 252
_OYNAKLIK_GUN = 60
BUYUK_Z = 2.5  # günlük getiri / 60 günlük std
BUYUK_EN_AZ = 0.02  # ve en az %2
ORAN_UC = 0.05  # 5 yıllık dağılımın alt/üst %5'i
ORAN_GUN = 252 * 5

TURLER = {
    "yukselis": "Sert Yükseliş",
    "dusus": "Sert Düşüş",
    "zirve_52": "52 Hafta Zirvesi",
    "dip_52": "52 Hafta Dibi",
}


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
    seviye: float  # yukselis/dusus: z; zirve/dip: önceki 52 hafta seviyesi


def _getiri(c: pd.Series, gun: int) -> float | None:
    return float(c.iloc[-1] / c.iloc[-1 - gun] - 1) if len(c) > gun else None


def olc(sembol: str, df: pd.DataFrame) -> Olcum | None:
    c = df["Close"].astype(float).dropna()
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
        g1h=_getiri(c, 5),
        g1a=_getiri(c, 21),
        gyb=float(c.iloc[-1] / once.iloc[-1] - 1) if len(once) else None,
        z=float(r.iloc[-1] / std) if std else None,
    )


def sinyaller(sembol: str, df: pd.DataFrame, o: Olcum) -> list[Sinyal]:
    out: list[Sinyal] = []
    if o.z is not None and abs(o.z) >= BUYUK_Z and abs(o.gunluk) >= BUYUK_EN_AZ:
        tur = "yukselis" if o.gunluk > 0 else "dusus"
        out.append(Sinyal(tur, sembol, o.kapanis, o.gunluk, o.z))
    c = df["Close"].astype(float).dropna()
    if len(c) > DONEM:
        onceki = c.iloc[-1 - DONEM : -1]
        ust, alt = float(onceki.max()), float(onceki.min())
        if o.kapanis > ust:
            out.append(Sinyal("zirve_52", sembol, o.kapanis, o.gunluk, ust))
        elif o.kapanis < alt:
            out.append(Sinyal("dip_52", sembol, o.kapanis, o.gunluk, alt))
    return out


@dataclass(frozen=True)
class OranOlcum:
    oran: Oran
    seri: pd.Series
    deger: float
    yuzdelik: float  # son 5 yılda bugünkü değerin altında kalan günlerin payı
    g1a: float | None

    @property
    def uc(self) -> bool:
        return self.yuzdelik <= ORAN_UC or self.yuzdelik >= 1 - ORAN_UC


def oran_serisi(tablolar: dict[str, pd.DataFrame], pay: str, payda: str) -> pd.Series:
    a = tablolar[pay]["Close"].astype(float)
    b = tablolar[payda]["Close"].astype(float)
    return (a / b).dropna()


def oranlar(tablolar: dict[str, pd.DataFrame]) -> list[OranOlcum]:
    out: list[OranOlcum] = []
    for o in ORANLAR:
        if o.pay not in tablolar or o.payda not in tablolar:
            continue
        s = oran_serisi(tablolar, o.pay, o.payda).iloc[-ORAN_GUN:]
        if len(s) < DONEM:
            continue
        son = float(s.iloc[-1])
        out.append(
            OranOlcum(o, s, son, float((s.iloc[:-1] < son).mean()), _getiri(s, 21)),
        )
    return out


def gram_altin(tablolar: dict[str, pd.DataFrame]) -> pd.Series | None:
    """TL/gram: ons altın (GC=F) × USD/TRY / 31,10; iki serinin ortak günlerinde."""
    if "GC=F" not in tablolar or "TRY=X" not in tablolar:
        return None
    ons = tablolar["GC=F"]["Close"].astype(float)
    kur = tablolar["TRY=X"]["Close"].astype(float)
    kur.index = pd.DatetimeIndex(kur.index).normalize()
    ons.index = pd.DatetimeIndex(ons.index).normalize()
    s = (ons * kur.reindex(ons.index).ffill() / ONS_GRAM).dropna()
    return s if len(s) else None


def rekor_mu(s: pd.Series) -> bool:
    return len(s) > 1 and float(s.iloc[-1]) > float(s.iloc[:-1].max())
