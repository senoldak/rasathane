"""Borsa İstanbul varant (.V) enstrüman adını çözer.

Ad sağdan sabit genişlikle okunur:
dayanak + tür(C/P, 1) + vade(GGAAYY, 6) + kullanım(7) + ihraççı(3) + çarpan(7) + "NA".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

VARANT_TIPLERI = {"MSPOTECW": "C", "MSPOTEPW": "P"}

_AD = re.compile(
    r"^(?P<dayanak>.+)(?P<tur>[CP])(?P<vade>\d{6})"
    r"(?P<kullanim>[\d.]{7})(?P<ihracci>[A-Z0-9]{3})(?P<carpan>[\d.]{7})NA$"
)


@dataclass(frozen=True)
class VarantSarti:
    dayanak: str
    tur: str  # "C" / "P"
    vade: date
    kullanim: float
    ihracci: str
    carpan: float


def varant_adi_coz(ad: str) -> VarantSarti | None:
    """Adı çözer; biçime uymuyorsa None döner."""
    e = _AD.match(ad)
    if e is None:
        return None
    v = e["vade"]
    try:
        vade = date(2000 + int(v[4:]), int(v[2:4]), int(v[:2]))
        kullanim = float(e["kullanim"])
        carpan = float(e["carpan"])
    except ValueError:
        return None
    return VarantSarti(e["dayanak"], e["tur"], vade, kullanim, e["ihracci"], carpan)
