# src/opsi/kanal/iv.py
"""Kanal kartlarının saf IV hesapları: IV30, 25 delta put skew, beklenen hareket.

IV, kontrat fiyatından yeniden hesaplanır; Yahoo'nun impliedVolatility alanı ve
pricer.enrich'in 0.30 geri dönüşü kullanılmaz (bulunamayan IV atlanır).
"""

import datetime
import math
from typing import TypedDict

from ..pricer import bs_put_delta, calculate_time_to_expiry, implied_vol_put
from ..types import RawContract

_IV_ALT, _IV_UST = 0.0011, 3.99  # implied_vol_put arama sınırlarına yapışan sonuç geçersiz
_MIN_FIYAT = 0.05
_MIN_HACIM, _MIN_OI = 5, 25  # ikisi birden altındaysa kontrat hesaba girmez
_MAKS_MAKAS = 0.5  # (satış − alış) / orta fiyat
_ATM_TOLERANS = 0.05
_DELTA_HEDEF, _DELTA_TOLERANS = -0.25, 0.08


class Nokta(TypedDict):
    expiry: str
    dte: int
    strike: float
    iv: float
    delta: float


def _fiyat(c: RawContract) -> float | None:
    """Güvenilir fiyat: dar makaslı orta fiyat ya da o gün işlem görmüşse son fiyat.

    Hacmi ve açık pozisyonu eşiğin altındaki ya da makası geniş kontrat atlanır
    (pricer.enrich ile aynı fiyat kuralı korunur: kotasyon varsa orta fiyat).
    """
    hacim, oi = c.get("volume") or 0, c.get("openInterest") or 0
    if hacim < _MIN_HACIM and oi < _MIN_OI:
        return None
    bid, ask = c.get("bid") or 0.0, c.get("ask") or 0.0
    if bid > 0 and ask >= bid:
        orta = 0.5 * (bid + ask)
        return orta if (ask - bid) / orta <= _MAKS_MAKAS else None
    if hacim > 0:
        return c.get("lastPrice") or 0.0
    return None


def gecerli_noktalar(
    chain: list[RawContract],
    spot: float,
    r: float = 0.045,
    now: datetime.datetime | None = None,
) -> list[Nokta]:
    """Fiyatı güvenilir ve IV'si bulunabilen put kontratları."""
    out: list[Nokta] = []
    for c in chain:
        p = _fiyat(c)
        if p is None or p <= _MIN_FIYAT:
            continue
        try:
            dte, t = calculate_time_to_expiry(c["expiry"], now=now)
            iv = implied_vol_put(p, spot, c["strike"], t, r, 0.0)
        except ValueError:
            continue
        if dte <= 0 or iv <= _IV_ALT or iv >= _IV_UST:
            continue
        delta = bs_put_delta(spot, c["strike"], t, r, 0.0, iv)
        out.append(
            {"expiry": c["expiry"], "dte": dte, "strike": c["strike"], "iv": iv, "delta": delta}
        )
    return out


def atm_iv(noktalar: list[Nokta], expiry: str, spot: float) -> float | None:
    vade = [n for n in noktalar if n["expiry"] == expiry]
    if not vade:
        return None
    en_yakin = min(vade, key=lambda n: abs(n["strike"] - spot))
    if abs(en_yakin["strike"] / spot - 1) > _ATM_TOLERANS:
        return None
    return en_yakin["iv"]


def _vade_atm(noktalar: list[Nokta], spot: float, lo: int, hi: int) -> list[tuple[int, float]]:
    """[(dte, atm_iv)] DTE sıralı, lo..hi aralığında ATM'si kurulabilen vadeler."""
    vadeler = sorted({(n["dte"], n["expiry"]) for n in noktalar if lo <= n["dte"] <= hi})
    out: list[tuple[int, float]] = []
    for dte, exp in vadeler:
        a = atm_iv(noktalar, exp, spot)
        if a is not None:
            out.append((dte, a))
    return out


def iv30(noktalar: list[Nokta], spot: float) -> float | None:
    """Sabit 30 günlük ATM IV: 30'u çevreleyen iki vade arasında toplam varyans ara değeri."""
    v = _vade_atm(noktalar, spot, 7, 90)
    alt = [x for x in v if x[0] <= 30]
    ust = [x for x in v if x[0] >= 30]
    if alt and ust:
        (d1, s1), (d2, s2) = alt[-1], ust[0]
        if d1 == d2:
            return s1
        w1, w2 = s1 * s1 * d1, s2 * s2 * d2
        w30 = w1 + (w2 - w1) * (30 - d1) / (d2 - d1)
        return math.sqrt(w30 / 30) if w30 > 0 else None
    yakin = [x for x in v if 20 <= x[0] <= 45]
    if not yakin:
        return None
    return min(yakin, key=lambda x: abs(x[0] - 30))[1]


def skew25(noktalar: list[Nokta], spot: float) -> float | None:
    """~30 gün vadede 25 delta put IV'si / ATM IV."""
    vadeler = sorted({(n["dte"], n["expiry"]) for n in noktalar if 20 <= n["dte"] <= 45})
    if not vadeler:
        return None
    _, exp = min(vadeler, key=lambda x: abs(x[0] - 30))
    atm = atm_iv(noktalar, exp, spot)
    vade = [n for n in noktalar if n["expiry"] == exp]
    if atm is None or not vade:
        return None
    n25 = min(vade, key=lambda n: abs(n["delta"] - _DELTA_HEDEF))
    if abs(n25["delta"] - _DELTA_HEDEF) > _DELTA_TOLERANS:
        return None
    return n25["iv"] / atm


def beklenen_hareket(spot: float, iv: float, dte: int) -> tuple[float, float, float]:
    """(yüzde, alt, üst): bir standart sapmalık hareket."""
    y = iv * math.sqrt(dte / 365.0)
    return y, spot * (1 - y), spot * (1 + y)
