# src/opsi/kanal/kartlar.py
"""Üç kartın verisi: IV Sarsıntısı, Aşağı Yön Primi, Haftanın 5 Nakit Teminatlı Put Hissesi."""

import statistics
from typing import TypedDict

from .gecmis import Kayit, iv_konum, iv_seri
from .iv import beklenen_hareket
from .olcum import CspAday

_SARSINTI_YARIM = 4
_PRIM_SATIR = 6
_CSP_SATIR, _CSP_MIN = 5, 3
_MAKS_BOSLUK = 5
_YAKIN_BILANCO = 7
_RANK_GUN = 252
_MIN_GECMIS = 20  # bundan kısa IV geçmişinde yüzdelik anlamsız

BANTLAR: list[tuple[str, float, float]] = [
    ("$2k–5k", 2000.0, 5000.0),
    ("$5k–15k", 5000.0, 15000.0),
]


class SarsintiSatiri(TypedDict):
    sembol: str
    ad: str
    kapanis: float
    fiyat_degisim: float
    iv_once: float
    iv_simdi: float
    iv_degisim: float
    bilanco: bool


class PrimSatiri(TypedDict):
    sembol: str
    ad: str
    kapanis: float
    skew: float
    fark: float


class PrimKarti(TypedDict):
    satirlar: list[PrimSatiri]
    medyan: float
    tum_skewler: list[float]


class CspSatiri(TypedDict):
    sembol: str
    ad: str
    fiyat: float
    hareket_yuzde: float
    hareket_alt: float
    hareket_ust: float
    iv30: float
    iv_konum: float | None  # geçmiş yetersizken boş (kartta "—")
    skor: float


class CspKarti(TypedDict):
    bant: str
    satirlar: list[CspSatiri]
    iv_etiket: str


def iv_sarsintisi(
    bugun: list[Kayit], onceki: list[Kayit], adlar: dict[str, str], bosluk_gun: int
) -> list[SarsintiSatiri] | None:
    """IV30'u en çok düşen 4 ve en çok yükselen 4; karşılaştırma 5 işlem gününden eskiyse None."""
    if bosluk_gun > _MAKS_BOSLUK:
        return None
    once = {k["sembol"]: k for k in onceki}
    satirlar: list[SarsintiSatiri] = []
    for k in bugun:
        o = once.get(k["sembol"])
        if o is None or k["iv30"] is None or o["iv30"] is None or o["iv30"] <= 0:
            continue
        ob = o["bilanco_gun"]
        kb = k["bilanco_gun"]
        bilanco = (kb is not None and 0 <= kb <= _YAKIN_BILANCO) or (
            ob is not None and 0 <= ob <= bosluk_gun + 1
        )
        satirlar.append(
            {
                "sembol": k["sembol"],
                "ad": adlar.get(k["sembol"], k["sembol"]),
                "kapanis": k["kapanis"],
                "fiyat_degisim": k["kapanis"] / o["kapanis"] - 1 if o["kapanis"] else 0.0,
                "iv_once": o["iv30"],
                "iv_simdi": k["iv30"],
                "iv_degisim": k["iv30"] / o["iv30"] - 1,
                "bilanco": bilanco,
            }
        )
    if len(satirlar) < 2 * _SARSINTI_YARIM:
        return None
    satirlar.sort(key=lambda r: r["iv_degisim"])
    dusen = satirlar[:_SARSINTI_YARIM]
    yukselen = list(reversed(satirlar[-_SARSINTI_YARIM:]))
    return dusen + yukselen


def asagi_yon_primi(bugun: list[Kayit], adlar: dict[str, str]) -> PrimKarti | None:
    """25 delta put skew'u en yüksek 6 hisse, evren ortancasına göre farkıyla."""
    var = [k for k in bugun if k["skew25"] is not None]
    if len(var) < _PRIM_SATIR:
        return None
    skewler = [k["skew25"] for k in var if k["skew25"] is not None]
    medyan = statistics.median(skewler)
    var.sort(key=lambda k: -(k["skew25"] or 0.0))
    satirlar: list[PrimSatiri] = []
    for k in var[:_PRIM_SATIR]:
        s = k["skew25"] or 0.0
        satirlar.append(
            {
                "sembol": k["sembol"],
                "ad": adlar.get(k["sembol"], k["sembol"]),
                "kapanis": k["kapanis"],
                "skew": s,
                "fark": s - medyan,
            }
        )
    return {"satirlar": satirlar, "medyan": medyan, "tum_skewler": skewler}


def _bantta(sermaye: float, alt: float, ust: float, son: bool) -> bool:
    return alt <= sermaye < ust or (son and sermaye == ust)


def csp_kartlari(
    adaylar: list[CspAday], bugun: list[Kayit], gecmis: list[Kayit], adlar: dict[str, str]
) -> list[CspKarti]:
    """Sermaye bandı başına skora göre ilk 5; 3'ten az adayı olan bant atlanır."""
    bugunku = {k["sembol"]: k for k in bugun}
    if not bugunku:
        return []
    tarih = max(k["tarih"] for k in bugun)
    tum = {(k["tarih"], k["sembol"]): k for k in [*gecmis, *bugun]}
    kayitlar = list(tum.values())
    kartlar: list[CspKarti] = []
    for i, (ad, alt, ust) in enumerate(BANTLAR):
        son = i == len(BANTLAR) - 1
        secilen = sorted(
            (
                a
                for a in adaylar
                if _bantta(a["sermaye"], alt, ust, son)
                and a["sembol"] in bugunku
                and bugunku[a["sembol"]]["iv30"] is not None
            ),
            key=lambda a: -a["skor"],
        )[:_CSP_SATIR]
        if len(secilen) < _CSP_MIN:
            continue
        seriler = {a["sembol"]: iv_seri(kayitlar, a["sembol"], tarih) for a in secilen}
        en_kisa = min(len(s) for s in seriler.values())
        ilk_tarih = max(
            min(
                k["tarih"] for k in kayitlar if k["sembol"] == a["sembol"] and k["iv30"] is not None
            )
            for a in secilen
        )
        satirlar: list[CspSatiri] = []
        etiket = ""
        for a in secilen:
            k = bugunku[a["sembol"]]
            v30 = k["iv30"] or 0.0
            seri = seriler[a["sembol"]]
            if en_kisa < _RANK_GUN:
                seri = seri[-(_RANK_GUN - 1) :]
            konum_v, etiket = iv_konum(seri, ilk_tarih)
            konum = konum_v if len(seri) >= _MIN_GECMIS else None
            y, lo, hi = beklenen_hareket(k["kapanis"], v30, a["dte"])
            satirlar.append(
                {
                    "sembol": a["sembol"],
                    "ad": adlar.get(a["sembol"], a["sembol"]),
                    "fiyat": k["kapanis"],
                    "hareket_yuzde": y,
                    "hareket_alt": lo,
                    "hareket_ust": hi,
                    "iv30": v30,
                    "iv_konum": konum,
                    "skor": a["skor"],
                }
            )
        kartlar.append({"bant": ad, "satirlar": satirlar, "iv_etiket": etiket})
    return kartlar
