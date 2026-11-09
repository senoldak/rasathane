"""VİOP ve BIST 30 dayanak varlık eşlemesi ve opsiyon hesaplamaları.

Borsa İstanbul VİOP sözleşmelerindeki dayanak varlık kodları (XU030, THYAO, GARAN) ile
Yahoo Finance piyasa simgeleri (XU030.IS, THYAO.IS, GARAN.IS) arasında çift yönlü
dönüşüm ve Black-Scholes fiyatlama/Yunan harfleri hesaplamaları.
"""

from __future__ import annotations

import math
from typing import Mapping

# BIST 30 endeks bileşenleri ve standart VİOP dayanak kodları eşlemesi
BIST30_DAYANAK_ESLEMESI: Mapping[str, str] = {
    "AKBNK": "AKBNK.IS",
    "ALARK": "ALARK.IS",
    "ARCLK": "ARCLK.IS",
    "ASELS": "ASELS.IS",
    "ASTOR": "ASTOR.IS",
    "BIMAS": "BIMAS.IS",
    "BRSAN": "BRSAN.IS",
    "DOAS": "DOAS.IS",
    "EKGYO": "EKGYO.IS",
    "ENKAI": "ENKAI.IS",
    "EREGL": "EREGL.IS",
    "FROTO": "FROTO.IS",
    "GARAN": "GARAN.IS",
    "GUBRF": "GUBRF.IS",
    "HEKTS": "HEKTS.IS",
    "ISCTR": "ISCTR.IS",
    "KCHOL": "KCHOL.IS",
    "KONTR": "KONTR.IS",
    "KOZAL": "KOZAL.IS",
    "KRDMD": "KRDMD.IS",
    "MGROS": "MGROS.IS",
    "ODAS": "ODAS.IS",
    "OYAKC": "OYAKC.IS",
    "PETKM": "PETKM.IS",
    "PGSUS": "PGSUS.IS",
    "SAHOL": "SAHOL.IS",
    "SASA": "SASA.IS",
    "SISE": "SISE.IS",
    "TAVHL": "TAVHL.IS",
    "TCELL": "TCELL.IS",
    "THYAO": "THYAO.IS",
    "TOASO": "TOASO.IS",
    "TUPRS": "TUPRS.IS",
    "VAKBN": "VAKBN.IS",
    "YKBNK": "YKBNK.IS",
}

# Endeks ve Makro / Döviz / Emtia Dayanak Eşlemesi
MAKRO_DAYANAK_ESLEMESI: Mapping[str, str] = {
    "XU030": "XU030.IS",
    "XU100": "XU100.IS",
    "USDTRY": "TRY=X",
    "EURTRY": "EURTRY=X",
    "EURUSD": "EURUSD=X",
    "GBPTRY": "GBPTRY=X",
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
}

# Birleşik arama sözlüğü
TUM_DAYANAKLAR: dict[str, str] = {**BIST30_DAYANAK_ESLEMESI, **MAKRO_DAYANAK_ESLEMESI}
TERS_DAYANAKLAR: dict[str, str] = {v: k for k, v in TUM_DAYANAKLAR.items()}

OYNAKLIK_ALT = 0.01
OYNAKLIK_UST = 5.0
TOLERANS = 1e-6


def dayanak_to_yahoo(dayanak: str) -> str:
    """VİOP dayanak kodunu (ör. 'THYAO', 'XU030', 'USDTRY') Yahoo sembolüne dönüştürür."""
    kod = dayanak.strip().upper()
    if kod in TUM_DAYANAKLAR:
        return TUM_DAYANAKLAR[kod]
    # Bilinmeyen hisse ise varsayılan olarak BIST eki ekle
    if not kod.endswith(".IS") and not "=" in kod:
        return f"{kod}.IS"
    return kod


def yahoo_to_dayanak(sembol: str) -> str:
    """Yahoo sembolünü (ör. 'THYAO.IS', 'TRY=X') VİOP dayanak koduna dönüştürür."""
    s = sembol.strip().upper()
    if s in TERS_DAYANAKLAR:
        return TERS_DAYANAKLAR[s]
    if s.endswith(".IS"):
        return s[:-3]
    return s


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(
    spot: float, kullanim: float, yil: float, faiz: float, oynaklik: float
) -> tuple[float, float]:
    kok = oynaklik * math.sqrt(yil)
    d1 = (math.log(spot / kullanim) + (faiz + 0.5 * oynaklik * oynaklik) * yil) / kok
    return d1, d1 - kok


def _ic_deger(spot: float, kullanim: float, tur: str) -> float:
    return max(spot - kullanim, 0.0) if tur == "C" else max(kullanim - spot, 0.0)


def bs_fiyat(
    spot: float, kullanim: float, yil: float, faiz: float, oynaklik: float, tur: str
) -> float:
    """Avrupa tipi alım ('C') ya da satım ('P') opsiyonunun teorik fiyatı."""
    if yil <= 0 or oynaklik <= 0:
        return _ic_deger(spot, kullanim, tur)
    d1, d2 = _d1_d2(spot, kullanim, yil, faiz, oynaklik)
    iskonto = math.exp(-faiz * yil)
    if tur == "C":
        return spot * _ncdf(d1) - kullanim * iskonto * _ncdf(d2)
    return kullanim * iskonto * _ncdf(-d2) - spot * _ncdf(-d1)


def bs_delta(
    spot: float, kullanim: float, yil: float, faiz: float, oynaklik: float, tur: str
) -> float:
    """Alım için 0..1, satım için -1..0 delta değeri."""
    if yil <= 0 or oynaklik <= 0:
        if tur == "C":
            return 1.0 if spot > kullanim else 0.0
        return -1.0 if spot < kullanim else 0.0
    d1, _ = _d1_d2(spot, kullanim, yil, faiz, oynaklik)
    return _ncdf(d1) if tur == "C" else _ncdf(d1) - 1.0


def bs_teta_gunluk(
    spot: float, kullanim: float, yil: float, faiz: float, oynaklik: float, tur: str
) -> float:
    """Takvim günü başına değer kaybı (zaman erimesi)."""
    if yil <= 0 or oynaklik <= 0:
        return 0.0
    d1, d2 = _d1_d2(spot, kullanim, yil, faiz, oynaklik)
    iskonto = math.exp(-faiz * yil)
    zaman = -spot * _npdf(d1) * oynaklik / (2.0 * math.sqrt(yil))
    if tur == "C":
        yillik = zaman - faiz * kullanim * iskonto * _ncdf(d2)
    else:
        yillik = zaman + faiz * kullanim * iskonto * _ncdf(-d2)
    return yillik / 365.0


def etkin_kaldirac(
    delta: float, spot: float, varant_fiyati: float, carpan: float, kur: float = 1.0
) -> float:
    """Varant veya opsiyon için etkin kaldıraç: |delta| * spot * çarpan * kur / prim."""
    if varant_fiyati <= 0:
        return 0.0
    return abs(delta) * spot * carpan * kur / varant_fiyati


def ortuk_oynaklik(
    fiyat: float, spot: float, kullanim: float, yil: float, faiz: float, tur: str
) -> float | None:
    """Piyasa fiyatından örtük oynaklığı (IV) bisection yöntemiyle çözer."""
    if yil <= 0:
        return None
    alt, ust = OYNAKLIK_ALT, OYNAKLIK_UST
    if bs_fiyat(spot, kullanim, yil, faiz, alt, tur) > fiyat:
        return None
    if bs_fiyat(spot, kullanim, yil, faiz, ust, tur) < fiyat:
        return None
    while ust - alt > TOLERANS:
        orta = 0.5 * (alt + ust)
        if bs_fiyat(spot, kullanim, yil, faiz, orta, tur) < fiyat:
            alt = orta
        else:
            ust = orta
    return 0.5 * (alt + ust)
