"""Kurlar arası analizler: carry, risk iştahı, emtia/faiz bağları, seanslar, faiz farkları,
Fed beklentisi, sinyal karnesi ve kura duyarlı hisseler."""

import datetime
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .evren import ADLAR, BAGLAR, GUVENLI, PARA_KURU, RISKLI, Bag
from .tarama import DONEM, YILLIK, YON, getiri, kapanis, yuzdelik

BES_YIL = DONEM * 5


def guc(para: str, tablolar: dict[str, pd.DataFrame]) -> pd.Series | None:
    """Para biriminin USD karşısındaki değeri (yükselince para birimi güçlenir)."""
    k = PARA_KURU.get(para)
    if k is None or k.sembol not in tablolar:
        return None
    c = kapanis(tablolar[k.sembol])
    return 1 / c if k.usd_bazli else c


# --- carry ---


@dataclass(frozen=True)
class Carry:
    para: str
    faiz: float  # yüzde
    fark: float  # USD faizine göre, yüzde puan
    oynaklik: float  # 3 aylık yıllık oynaklık, oran
    g1a: float | None  # USD karşısında 1 aylık getiri

    @property
    def oran(self) -> float:
        return self.fark / 100 / self.oynaklik if self.oynaklik else 0.0


def carry(faizler: dict[str, float], tablolar: dict[str, pd.DataFrame]) -> list[Carry]:
    if "USD" not in faizler:
        return []
    out: list[Carry] = []
    for para, faiz in faizler.items():
        g = guc(para, tablolar) if para != "USD" else None
        if g is None or len(g) < 64:
            continue
        oyn = float(g.apply(np.log).diff().iloc[-63:].std() * YILLIK)
        out.append(Carry(para, faiz, faiz - faizler["USD"], oyn, getiri(g, 21)))
    return sorted(out, key=lambda c: -c.oran)


# --- risk iştahı ---


@dataclass(frozen=True)
class RiskSatiri:
    para: str
    riskli: bool
    gunluk: float | None
    g1h: float | None
    g1a: float | None


@dataclass(frozen=True)
class Risk:
    satirlar: list[RiskSatiri]
    skor: pd.Series  # birikimli (riskli − güvenli) günlük getiri farkı
    gunluk: float
    g1a: float
    yuzdelik: float  # 1 aylık farkın son 5 yıldaki yüzdeliği


def risk(tablolar: dict[str, pd.DataFrame]) -> Risk | None:
    seriler = {p: guc(p, tablolar) for p in (*RISKLI, *GUVENLI)}
    var = {p: s for p, s in seriler.items() if s is not None and len(s) > DONEM}
    r = [p for p in RISKLI if p in var]
    g = [p for p in GUVENLI if p in var]
    if not r or not g:
        return None
    getiriler = pd.DataFrame({p: var[p].pct_change() for p in var}).iloc[-BES_YIL:]
    fark = (getiriler[r].mean(axis=1) - getiriler[g].mean(axis=1)).dropna()
    aylik = fark.rolling(21).sum().dropna()
    satirlar = [
        RiskSatiri(p, p in RISKLI, getiri(var[p], 1), getiri(var[p], 5), getiri(var[p], 21))
        for p in (*r, *g)
    ]
    return Risk(
        satirlar,
        fark.cumsum(),
        float(fark.iloc[-1]),
        float(aylik.iloc[-1]),
        yuzdelik(aylik),
    )


# --- emtia ve faiz bağları ---

KOR_GUN = 60
KOR_KIRILMA = 0.5  # 60 günlük korelasyon 1 yıllığından bu kadar ayrılırsa


@dataclass(frozen=True)
class BagOlcum:
    bag: Bag
    kisa: float  # 60 günlük korelasyon
    uzun: float  # 1 yıllık
    seri: pd.Series  # kayan 60 günlük korelasyon

    @property
    def kirildi(self) -> bool:
        return abs(self.kisa - self.uzun) >= KOR_KIRILMA


def baglar(tablolar: dict[str, pd.DataFrame]) -> list[BagOlcum]:
    out: list[BagOlcum] = []
    for b in BAGLAR:
        k = ADLAR.get(b.kur)
        if b.kur not in tablolar or b.dis not in tablolar:
            continue
        kur = kapanis(tablolar[b.kur])
        if k is not None and k.usd_bazli and not b.fark:
            kur = 1 / kur  # para biriminin gücü: CAD ve NOK için petrolle aynı yönde
        dis = kapanis(tablolar[b.dis])
        df = pd.DataFrame(
            {"kur": kur.pct_change(), "dis": dis.diff() if b.fark else dis.pct_change()}
        ).dropna()
        if len(df) < DONEM + KOR_GUN:
            continue
        seri = df["kur"].rolling(KOR_GUN).corr(df["dis"]).dropna()
        uzun = float(df["kur"].iloc[-DONEM:].corr(df["dis"].iloc[-DONEM:]))
        out.append(BagOlcum(b, float(seri.iloc[-1]), uzun, seri.iloc[-DONEM * 2 :]))
    return out


# --- oynaklık tablosu ---


@dataclass(frozen=True)
class Oynaklik:
    sembol: str
    ay: float
    ceyrek: float
    yuzdelik: float  # 1 aylık oynaklığın 5 yıllık yüzdeliği


def oynakliklar(tablolar: dict[str, pd.DataFrame], semboller: list[str]) -> list[Oynaklik]:
    out: list[Oynaklik] = []
    for s in semboller:
        if s not in tablolar:
            continue
        lg = kapanis(tablolar[s]).apply(np.log).diff()
        ay = (lg.rolling(21).std() * YILLIK).dropna().iloc[-BES_YIL:]
        if len(ay) < DONEM:
            continue
        out.append(
            Oynaklik(s, float(ay.iloc[-1]), float(lg.iloc[-63:].std() * YILLIK), yuzdelik(ay))
        )
    return sorted(out, key=lambda o: -o.yuzdelik)


# --- seanslar ---

SEANSLAR = (("Asya", 23, 7), ("Londra", 7, 12), ("New York", 12, 21))  # UTC saat aralıkları


def _seans(saat: int) -> str | None:
    for ad_, bas, bit in SEANSLAR:
        if (bas <= saat < bit) if bas < bit else (saat >= bas or saat < bit):
            return ad_
    return None


def seanslar(saatlik: dict[str, pd.DataFrame], gun: int = 5) -> dict[str, dict[str, float]]:
    """sembol → seans → son `gun` günde seans başına ortalama mutlak hareket (oran)."""
    out: dict[str, dict[str, float]] = {}
    for s, df in saatlik.items():
        c = df["Close"].astype(float).dropna()
        idx = pd.DatetimeIndex(c.index)
        c.index = idx.tz_convert("UTC") if idx.tz is not None else idx.tz_localize("UTC")
        r = c.apply(np.log).diff().dropna().abs()
        gunler = sorted({t.date() for t in r.index})[-gun:]
        if not gunler:
            continue
        r = r[[t.date() >= gunler[0] for t in r.index]]
        etiket = [_seans(t.hour) for t in r.index]
        toplam = r.groupby(etiket).sum()
        out[s] = {ad_: float(toplam.get(ad_, 0.0)) / len(gunler) for ad_, _, _ in SEANSLAR}
    return out


# --- faiz farkları ---


@dataclass(frozen=True)
class FaizFarki:
    ad: str
    kur: str
    fark: float  # yüzde puan
    fark_1a: float | None  # 1 ayda değişim, yüzde puan
    kur_1a: float | None
    korelasyon: float | None  # 1 yıl, haftalık değişimler


def faiz_farki(
    ad_: str, kur: str, a: pd.Series, b: pd.Series, tablolar: dict[str, pd.DataFrame]
) -> FaizFarki | None:
    fark = (a - b.reindex(a.index).ffill()).dropna()
    if len(fark) < 30 or kur not in tablolar:
        return None
    k = kapanis(tablolar[kur])
    hafta = pd.DataFrame({"f": fark, "k": k}).ffill().dropna().resample("W-FRI").last()
    hafta = hafta.iloc[-52:]
    kor = float(hafta["f"].diff().corr(hafta["k"].pct_change())) if len(hafta) > 20 else None
    once = fark[fark.index <= fark.index[-1] - pd.Timedelta(days=30)]
    return FaizFarki(
        ad_,
        kur,
        float(fark.iloc[-1]),
        float(fark.iloc[-1] - once.iloc[-1]) if len(once) else None,
        getiri(k, 21),
        kor if kor is not None and not np.isnan(kor) else None,
    )


# --- Fed beklentisi ---

AY_KODU = "FGHJKMNQUVXZ"


def zq_sembolleri(bugun: datetime.date, ay: int = 10) -> list[tuple[str, datetime.date]]:
    out = []
    y, m = bugun.year, bugun.month
    for _ in range(ay):
        out.append((f"ZQ{AY_KODU[m - 1]}{y % 100:02d}.CBT", datetime.date(y, m, 1)))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


@dataclass(frozen=True)
class Beklenti:
    ay: datetime.date
    faiz: float  # vadeli fiyattan örtük ortalama faiz, yüzde
    fark: float  # bugünkü faize göre, baz puan
    degisim: float | None  # bir önceki kapanışa göre, baz puan


def fed_beklentisi(
    tablolar: dict[str, pd.DataFrame], bugun: datetime.date, simdiki: float
) -> list[Beklenti]:
    out: list[Beklenti] = []
    for s, ay in zq_sembolleri(bugun):
        if s not in tablolar:
            continue
        c = kapanis(tablolar[s])
        if not len(c):
            continue
        f = 100 - float(c.iloc[-1])
        d = (float(c.iloc[-2]) - float(c.iloc[-1])) * 100 if len(c) > 1 else None
        out.append(Beklenti(ay, f, (f - simdiki) * 100, d))
    return out


# --- sinyal karnesi ---

UFUKLAR = (5, 20, 60)


@dataclass(frozen=True)
class Karne:
    tur: str
    sayi: dict[int, int]
    ortalama: dict[int, float]  # sinyal yönünde ortalama getiri
    isabet: dict[int, float]


def karne(kayit: list[dict[str, str]], tablolar: dict[str, pd.DataFrame]) -> list[Karne]:
    out: list[Karne] = []
    for tur, yon in YON.items():
        getiriler: dict[int, list[float]] = {u: [] for u in UFUKLAR}
        for r in kayit:
            if r["tur"] != tur or r["sembol"] not in tablolar:
                continue
            c = kapanis(tablolar[r["sembol"]])
            yer = int(c.index.searchsorted(pd.Timestamp(r["tarih"])))
            if yer >= len(c) or c.index[yer].date().isoformat() != r["tarih"]:
                continue
            for u in UFUKLAR:
                if yer + u < len(c):
                    getiriler[u].append(yon * float(c.iloc[yer + u] / c.iloc[yer] - 1))
        if not getiriler[UFUKLAR[0]]:
            continue
        out.append(
            Karne(
                tur,
                {u: len(v) for u, v in getiriler.items()},
                {u: float(np.mean(v)) for u, v in getiriler.items() if v},
                {u: float(np.mean([x > 0 for x in v])) for u, v in getiriler.items() if v},
            )
        )
    return out


# --- kura duyarlı hisseler ---


@dataclass(frozen=True)
class Duyarlilik:
    kod: str
    beta: float  # USD/TRY'deki %1'lik haftalık harekete BIST 100'ün üzerindeki tepki, %
    r2: float


def duyarliliklar(
    hisseler: dict[str, pd.DataFrame], usdtry: pd.DataFrame, bist: pd.DataFrame
) -> list[Duyarlilik]:
    """Hissenin BIST 100'e göre fazla haftalık getirisinin USD/TRY haftalık getirisine eğimi."""
    k = kapanis(usdtry).resample("W-FRI").last().pct_change()
    x = kapanis(bist).resample("W-FRI").last().pct_change()
    out: list[Duyarlilik] = []
    for kod, df in hisseler.items():
        h = kapanis(df).resample("W-FRI").last().pct_change()
        d = pd.DataFrame({"y": h - x, "k": k}).dropna().iloc[-104:]
        if len(d) < 52 or float(d["k"].var()) == 0:
            continue
        beta = float(d["y"].cov(d["k"]) / d["k"].var())
        r2 = float(d["y"].corr(d["k"]) ** 2)
        out.append(Duyarlilik(kod.removesuffix(".IS"), beta, r2))
    return sorted(out, key=lambda d: -d.beta)
