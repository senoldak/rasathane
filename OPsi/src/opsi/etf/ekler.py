# src/opsi/etf/ekler.py
"""Haftalık ve günlük ek kartların hesabı: tema haritası, piyasa rejimi, yeni ETF'lerin seyri,
olağandışı opsiyon hareketi, fon akışı. Ağ yok; veri ag.py'den gelir."""

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .liste import Etf, tema_disi_mi
from .tarama import Olcum

# Ada göre tema; ilk eşleşen kazanır (özelden genele sıralı).
TEMALAR: list[tuple[str, str]] = [
    ("Uranyum ve nükleer", r"uranium|nuclear"),
    ("Denizcilik ve tanker", r"tanker|shipping|maritime|dry bulk|freight"),
    ("Altın madencileri", r"gold miner|junior gold"),
    ("Gümüş", r"silver"),
    ("Altın", r"\bgold\b"),
    ("Bakır ve metaller", r"copper|metals|mining|lithium|rare earth|battery"),
    ("Temiz enerji", r"clean|solar|wind|renewable|hydrogen"),
    ("Petrol ve gaz", r"\boil\b|natural gas|energy|exploration|\bmlp|midstream"),
    ("Yarı iletken", r"semiconductor|semi\b|chip"),
    ("Yapay zekâ ve robotik", r"artificial intelligence|\bai\b|robot|automation"),
    ("Siber güvenlik", r"cyber|security"),
    ("Kripto ve blokzincir", r"bitcoin|\bether|crypto|blockchain|digital asset"),
    ("Savunma ve havacılık", r"defense|aerospace|space"),
    ("Biyoteknoloji", r"biotech|genom"),
    ("Sağlık", r"health|medical|pharma"),
    ("Bankalar ve finans", r"bank|financial|insurance|broker"),
    ("Gayrimenkul", r"real estate|reit|homebuild"),
    ("Altyapı ve sanayi", r"infrastructure|industrial|transport"),
    ("Tarım ve emtia", r"agricultur|commodit|grain|timber|water"),
    ("Çin", r"china|chinese"),
    ("Hindistan", r"india"),
    ("Japonya", r"japan"),
    ("Latin Amerika", r"brazil|latin|mexic|argentin"),
    ("Gelişen piyasalar", r"emerging"),
    ("Avrupa", r"europe|germany|united kingdom|\buk\b|euro"),
    ("Uzun vadeli tahvil", r"20\+|long[- ]term treasury|long treasury"),
    ("Yüksek getirili tahvil", r"high yield|junk"),
    ("Volatilite", r"vix|volatility"),
]
_TEMA_DESEN = [(ad, re.compile(d, re.IGNORECASE)) for ad, d in TEMALAR]
TEMA_EN_AZ = 2  # bundan az ETF'li tema haritada yer almaz

# (ad, pay, payda, yükselirse anlamı)
REJIM: list[tuple[str, str, str, str]] = [
    ("Lüks / temel tüketim", "XLY", "XLP", "risk iştahı"),
    ("Yüksek getirili / Hazine", "HYG", "IEF", "kredi iştahı"),
    ("Bakır / altın", "CPER", "GLD", "büyüme beklentisi"),
    ("Küçük / büyük şirket", "IWM", "SPY", "geniş katılım"),
    ("Yarı iletken / piyasa", "SMH", "SPY", "teknoloji liderliği"),
    ("Gelişen / ABD", "EEM", "SPY", "dolar zayıflığı"),
]

OPSIYON_EN_AZ_DOLAR = 20_000_000.0
OPSIYON_EN_AZ_HACIM = 2000
OPSIYON_ORAN = 0.5  # günlük hacim / açık pozisyon
YENI_EN_ESKI = 45  # gün; yeni ETF seyri kartında listeye giriş üst sınırı
AKIS_GUN = 5


def tema_bul(ad: str) -> str | None:
    return next((t for t, d in _TEMA_DESEN if d.search(ad)), None)


@dataclass(frozen=True)
class TemaSatiri:
    tema: str
    sayi: int
    g1h: float
    g1a: float
    g3a: float
    onde: str  # temanın 1 aylık getiride en iyi ETF'si


def tema_haritasi(olcumler: dict[str, Olcum], kayit: dict[str, Etf]) -> list[TemaSatiri]:
    """Kaldıraçsız likit ETF'lerin tema başına ortanca getirileri, 1 aylığa göre sıralı."""
    gruplar: dict[str, list[Olcum]] = {}
    for s, o in olcumler.items():
        e = kayit.get(s)
        if e is None or tema_disi_mi(e) or None in (o.g1h, o.g1a, o.g3a):
            continue
        t = tema_bul(e["ad"])
        if t:
            gruplar.setdefault(t, []).append(o)
    out = [
        TemaSatiri(
            t,
            len(g),
            float(np.median([o.g1h or 0.0 for o in g])),
            float(np.median([o.g1a or 0.0 for o in g])),
            float(np.median([o.g3a or 0.0 for o in g])),
            max(g, key=lambda o: o.g1a or 0.0).sembol,
        )
        for t, g in gruplar.items()
        if len(g) >= TEMA_EN_AZ
    ]
    return sorted(out, key=lambda r: -r.g1a)


@dataclass(frozen=True)
class RejimSatiri:
    ad: str
    pay: str
    payda: str
    anlam: str
    oran: float
    g1a: float  # oranın 21 günlük değişimi
    sma50_ustu: bool


def rejim(tablolar: dict[str, pd.DataFrame]) -> list[RejimSatiri]:
    out: list[RejimSatiri] = []
    for ad, a, b, anlam in REJIM:
        if a not in tablolar or b not in tablolar:
            continue
        r = (tablolar[a]["Close"] / tablolar[b]["Close"]).dropna()
        if len(r) < 60:
            continue
        sma50 = float(r.iloc[-50:].mean())
        out.append(
            RejimSatiri(
                ad,
                a,
                b,
                anlam,
                float(r.iloc[-1]),
                float(r.iloc[-1] / r.iloc[-22] - 1),
                r.iloc[-1] > sma50,
            )
        )
    return out


@dataclass(frozen=True)
class YeniSeyir:
    sembol: str
    ad: str
    ilk_gorulme: str
    getiri: float  # ilk kapanıştan bu yana
    ilk_hacim: float  # ilk 5 günün ortalama işlem tutarı ($)
    son_hacim: float  # son 5 günün


def yeni_seyir(
    kayit: dict[str, Etf], tablolar: dict[str, pd.DataFrame], tarih: str, en_yeni: str
) -> list[YeniSeyir]:
    """Listeye en_yeni'den önce, son 45 gün içinde girmiş ETF'ler; son haftanın işlem tutarı
    büyümesine göre sıralı."""
    sinir = (pd.Timestamp(tarih) - pd.Timedelta(days=YENI_EN_ESKI)).date().isoformat()
    out: list[YeniSeyir] = []
    for e in kayit.values():
        g = e["ilk_gorulme"]
        if not g or not (sinir <= g < en_yeni) or e["sembol"] not in tablolar:
            continue
        df = tablolar[e["sembol"]]
        df = df[df.index >= pd.Timestamp(g) - pd.Timedelta(days=7)]
        if len(df) < 6 or df["Close"].iloc[0] <= 0:
            continue
        tutar = df["Close"] * df["Volume"]
        out.append(
            YeniSeyir(
                e["sembol"],
                e["ad"],
                g,
                float(df["Close"].iloc[-1] / df["Close"].iloc[0] - 1),
                float(tutar.iloc[:5].mean()),
                float(tutar.iloc[-5:].mean()),
            )
        )
    return sorted(out, key=lambda y: -(y.son_hacim / y.ilk_hacim if y.ilk_hacim > 0 else 0.0))


@dataclass(frozen=True)
class OpsiyonSatiri:
    sembol: str
    yon: str  # "çağrı" | "put"
    hacim: int
    acik: int  # açık pozisyon
    oran: float
    put_cagri: float  # toplam put hacmi / çağrı hacmi
    en_aktif: str  # ör. "45 C 21.11"


def opsiyon_ozeti(sembol: str, zincir: pd.DataFrame) -> list[OpsiyonSatiri]:
    """zincir sütunları: tur ("C"/"P"), strike, vade (YYYY-AA-GG), volume, openInterest.

    Hacmi açık pozisyonun yarısını aşan ve en az 2000 kontrat olan yön olağandışı sayılır.
    """
    if zincir.empty:
        return []
    z = zincir.fillna({"volume": 0, "openInterest": 0})
    hacimler = {t: float(z.loc[z["tur"] == t, "volume"].sum()) for t in ("C", "P")}
    out: list[OpsiyonSatiri] = []
    for t, yon in (("C", "çağrı"), ("P", "put")):
        parca = z[z["tur"] == t]
        h, a = int(parca["volume"].sum()), int(parca["openInterest"].sum())
        if h < OPSIYON_EN_AZ_HACIM or a <= 0 or h / a < OPSIYON_ORAN:
            continue
        en = parca.loc[parca["volume"].idxmax()]
        vade = pd.Timestamp(str(en["vade"])).strftime("%d.%m")
        out.append(
            OpsiyonSatiri(
                sembol,
                yon,
                h,
                a,
                h / a,
                hacimler["P"] / hacimler["C"] if hacimler["C"] > 0 else float("inf"),
                f"{float(en['strike']):g} {t} {vade}",
            )
        )
    return out


@dataclass(frozen=True)
class AkisSatiri:
    sembol: str
    ad: str
    akis: float  # tahmini net giriş ($): varlık değişiminden fiyat etkisi çıkarılmış
    oran: float  # akış / başlangıç varlığı


def fon_akisi(
    varliklar: pd.DataFrame, tablolar: dict[str, pd.DataFrame], adlar: dict[str, str], tarih: str
) -> list[AkisSatiri]:
    """varliklar: tarih, sembol, varlik (toplam varlık, $). Son kayıt ile 5 işlem günü önceki
    kayıt karşılaştırılır: akış = V_son − V_önce × (P_son / P_önce)."""
    out: list[AkisSatiri] = []
    if varliklar.empty:
        return out
    for s, g in varliklar.groupby("sembol"):
        g = g.sort_values("tarih")
        son = g[g["tarih"] == tarih]
        once = g[g["tarih"] < tarih]
        if son.empty or len(once) < AKIS_GUN or s not in tablolar:
            continue
        o = once.iloc[-AKIS_GUN]
        df = tablolar[str(s)]["Close"]
        p_once = df[df.index <= pd.Timestamp(o["tarih"])]
        if p_once.empty or o["varlik"] <= 0:
            continue
        v_son = float(son["varlik"].iloc[-1])
        akis = v_son - float(o["varlik"]) * float(df.iloc[-1] / p_once.iloc[-1])
        if v_son == float(o["varlik"]):
            continue  # Yahoo varlığı güncellememiş
        out.append(AkisSatiri(str(s), adlar.get(str(s), str(s)), akis, akis / float(o["varlik"])))
    return out
