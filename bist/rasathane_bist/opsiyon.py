"""Black-Scholes: Avrupa tipi, temettüsüz, sürekli bileşik faiz. `yil` takvim günü / 365."""

from __future__ import annotations

import math

OYNAKLIK_ALT = 0.01
OYNAKLIK_UST = 5.0
TOLERANS = 1e-6


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
    """Avrupa tipi alım ("C") ya da satım ("P") opsiyonunun fiyatı."""
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
    """Alım için 0..1, satım için -1..0."""
    if yil <= 0 or oynaklik <= 0:
        if tur == "C":
            return 1.0 if spot > kullanim else 0.0
        return -1.0 if spot < kullanim else 0.0
    d1, _ = _d1_d2(spot, kullanim, yil, faiz, oynaklik)
    return _ncdf(d1) if tur == "C" else _ncdf(d1) - 1.0


def bs_teta_gunluk(
    spot: float, kullanim: float, yil: float, faiz: float, oynaklik: float, tur: str
) -> float:
    """Takvim günü başına değer kaybı (alım ve satım için genelde negatif)."""
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


def ortuk_oynaklik(
    fiyat: float, spot: float, kullanim: float, yil: float, faiz: float, tur: str
) -> float | None:
    """Fiyattan oynaklığı ikiye bölmeyle çözer (0,01-5,0); aralık dışıysa None."""
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


def etkin_kaldirac(
    delta: float, spot: float, varant_fiyati: float, carpan: float, kur: float = 1.0
) -> float:
    """|delta| * spot * çarpan * kur / varant fiyatı."""
    return abs(delta) * spot * carpan * kur / varant_fiyati
