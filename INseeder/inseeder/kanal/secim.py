"""Kanal ölçütleri: günlük alım listesi, küme etiketi ve haftalık özet."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Set, Union

from inseeder.kanal.model import Beyan, pozisyon_degisimi
from inseeder.kanal.takvim import hafta_gunleri

ALIM_ESIGI = 100_000.0
SATIS_ESIGI = 5_000_000.0
SATIS_UNVANLARI = {"CEO", "CFO"}
GUNLUK_EN_COK = 8
KUME_EN_COK = 6
SATIS_EN_COK = 5
KUME_PENCERESI_GUN = 7


@dataclass
class Satir:
    beyan: Beyan
    kume: bool
    degisim: Union[float, str, None]


@dataclass
class KumeSatiri:
    sembol: str
    sirket: str
    kisi_sayisi: int
    toplam: float


@dataclass
class HaftalikOzet:
    gunler: List[date]
    kumeler: List[KumeSatiri]
    satislar: List[Beyan]


def alim_mi(b: Beyan) -> bool:
    return b.kod == "P" and not b.plan_10b5_1 and b.tutar >= ALIM_ESIGI


def buyuk_satis_mi(b: Beyan) -> bool:
    return (b.kod == "S" and not b.plan_10b5_1 and b.tutar >= SATIS_ESIGI
            and b.unvan in SATIS_UNVANLARI)


def kanala_uygun(b: Beyan) -> bool:
    return alim_mi(b) or buyuk_satis_mi(b)


def _tekil(beyanlar: List[Beyan], kosul, ilk: date, son: date) -> List[Beyan]:
    """Aralıkta koşulu sağlayan beyanlar; aynı işlemi tekrarlayan beyanlar tek sayılır.

    Form 4 bir beyanda en çok 10 raporlayan kişi alır; daha kalabalık gruplar aynı
    alımı ikinci bir beyanla tekrarlar (aynı gün, şirket, adet ve fiyat).
    """
    tekil: Dict[tuple, Beyan] = {}
    for b in beyanlar:
        if kosul(b) and ilk <= b.dosyalama_gunu <= son:
            anahtar = (b.sembol, b.dosyalama_gunu, b.kod, b.adet, round(b.ort_fiyat, 4))
            tekil.setdefault(anahtar, b)
    return list(tekil.values())


def _alimlar(beyanlar: List[Beyan], ilk: date, son: date) -> List[Beyan]:
    return _tekil(beyanlar, alim_mi, ilk, son)


def _kisiler(beyanlar: List[Beyan], ilk: date, son: date) -> Dict[str, Set[str]]:
    kisiler: Dict[str, Set[str]] = defaultdict(set)
    for b in _alimlar(beyanlar, ilk, son):
        kisiler[b.sembol].add(b.kisi)
    return kisiler


def gunluk_alimlar(beyanlar: List[Beyan], gun: date) -> List[Satir]:
    kisiler = _kisiler(beyanlar, gun - timedelta(days=KUME_PENCERESI_GUN - 1), gun)
    gunun = sorted(_alimlar(beyanlar, gun, gun),
                   key=lambda b: b.tutar, reverse=True)[:GUNLUK_EN_COK]
    return [Satir(b, len(kisiler[b.sembol]) >= 2, pozisyon_degisimi(b)) for b in gunun]


def haftalik_ozet(beyanlar: List[Beyan], herhangi_gun: date) -> HaftalikOzet:
    gunler = hafta_gunleri(herhangi_gun)
    ilk, son = gunler[0], gunler[-1]
    kisiler = _kisiler(beyanlar, ilk, son)
    toplam: Dict[str, float] = defaultdict(float)
    sirket: Dict[str, str] = {}
    for b in _alimlar(beyanlar, ilk, son):
        toplam[b.sembol] += b.tutar
        sirket[b.sembol] = b.sirket
    kumeler = sorted(
        (KumeSatiri(s, sirket[s], len(k), toplam[s]) for s, k in kisiler.items() if len(k) >= 2),
        key=lambda k: (k.kisi_sayisi, k.toplam), reverse=True,
    )[:KUME_EN_COK]
    satislar = sorted(
        _tekil(beyanlar, buyuk_satis_mi, ilk, son),
        key=lambda b: b.tutar, reverse=True,
    )[:SATIS_EN_COK]
    return HaftalikOzet(gunler, kumeler, satislar)
