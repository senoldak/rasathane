# src/opsi/kanal/grafik.py
"""OPsi Oynaklık grafiği: günün öne çıkan hissesinde IV30 ile gerçekleşen oynaklığın karşılaştırması."""

import datetime
import itertools
import math
import statistics
from collections.abc import Callable

from rasathane_ortak import kagit
from rasathane_ortak.kagit import Grafik, Hucre

from .cizim import FIKIR, KAYNAK
from .gecmis import Kayit
from .kartlar import PrimKarti, SarsintiSatiri

AD = "Oynaklık"
PENCERE = 20
GUN_SAYISI = 92
FiyatGecmisi = Callable[[str, str], list[tuple[str, float]]]


def oynaklik_secimi(
    prim: PrimKarti | None, sarsinti: list[SarsintiSatiri] | None
) -> tuple[str, str] | None:
    """Prim kartının ilk hissesi; prim yoksa sarsıntı kartının ilk hissesi."""
    if prim and prim["satirlar"]:
        return prim["satirlar"][0]["sembol"], "aşağı yön primi en yüksek"
    if sarsinti:
        return sarsinti[0]["sembol"], "IV sarsıntısı en sert"
    return None


def gerceklesen_oynaklik(kapanislar: list[float], pencere: int = PENCERE) -> list[float]:
    """Her gün için son `pencere` günlük log getirinin örneklem sapması × √252 (yıllık, oran)."""
    getiri = [math.log(b / a) for a, b in itertools.pairwise(kapanislar)]
    return [
        statistics.stdev(getiri[i - pencere : i]) * math.sqrt(252)
        for i in range(pencere, len(getiri) + 1)
    ]


def _yuzde(x: float) -> str:
    return f"%{x:.1f}".replace(".", ",")


def oynaklik_grafigi(
    sembol: str,
    ad: str,
    gerekce: str,
    tarih: str,
    kayit: Kayit,
    fiyatlar: list[tuple[str, float]],
) -> Grafik:
    iv30 = kayit["iv30"]
    if iv30 is None:
        raise ValueError(f"{sembol} için IV30 yok")
    bugun = datetime.date.fromisoformat(tarih)
    seri = [(datetime.date.fromisoformat(g), v) for g, v in fiyatlar if g <= tarih]
    rv = gerceklesen_oynaklik([v for _, v in seri])
    gunler = [g for g, _ in seri][PENCERE:]
    pencere = [
        (g, r * 100) for g, r in zip(gunler, rv) if g >= bugun - datetime.timedelta(days=GUN_SAYISI)
    ]
    if len(pencere) < 2:
        raise ValueError(f"{sembol} için yeterli fiyat geçmişi yok")
    iv = round(iv30 * 100, 1)
    son_rv = pencere[-1][1]
    gun = kayit["bilanco_gun"]
    if gun is None:
        alt = gerekce
    elif gun == 0:
        alt = f"{gerekce} · bilanço bugün"
    else:
        alt = f"{gerekce} · bilançoya {gun} gün"
    fark = iv - son_rv
    return Grafik(
        fikir=FIKIR,
        tarih=kagit.tarih_metni(bugun),
        baslik=f"{sembol} · {ad}",
        alt_baslik=alt,
        ozet=(
            ("IV30 bugün", Hucre(_yuzde(iv), vurgu=True)),
            ("Gerçekleşen 20g", Hucre(_yuzde(son_rv))),
            ("Fark", Hucre(f"{'+' if fark >= 0 else '−'}{abs(fark):.1f} puan".replace(".", ","))),
        ),
        gunler=tuple(g for g, _ in pencere),
        seri=tuple(v for _, v in pencere),
        kaynak=KAYNAK,
        seri_adi="gerçekleşen oynaklık (20g)",
        yatay=iv,
        yatay_etiket=f"IV30 {_yuzde(iv)}",
        yuzde_eksen=True,
    )
