from datetime import date, timedelta
from typing import Dict, List, Set

# ABD federal tatilleri (hafta sonuna denk gelenler gözlenen günüyle). SEC/EDGAR bu günlerde kapalıdır;
# Columbus ve Veterans Day'de NYSE açık olsa da EDGAR günlük dizini oluşmaz. Good Friday'de ise NYSE
# kapalı, SEC açıktır. Bu yüzden takvim NYSE'ye değil federal tatillere göre tutulur.
# Yeni yıl gelmeden listeye eklenmeli.
_FEDERAL: Dict[int, Set[date]] = {
    2026: {date(2026, a, g) for a, g in [(1, 1), (1, 19), (2, 16), (5, 25), (6, 19), (7, 3), (9, 7),
                                          (10, 12), (11, 11), (11, 26), (12, 25)]},
    2027: {date(2027, a, g) for a, g in [(1, 1), (1, 18), (2, 15), (5, 31), (6, 18), (7, 5), (9, 6),
                                          (10, 11), (11, 11), (11, 25), (12, 24)]},
}


class TakvimHatasi(Exception):
    pass


def _yil_kontrol(g: date) -> None:
    if g.year not in _FEDERAL:
        raise TakvimHatasi(f"ABD federal tatil listesi {g.year} için yok; takvim.py güncellenmeli")


def is_gunu_mu(g: date) -> bool:
    """Hafta içi gün: ClinicalTrials.gov güncellemeleri yalnız bu günler için sorgulanır."""
    _yil_kontrol(g)
    return g.weekday() < 5


def edgar_acik_mi(g: date) -> bool:
    return is_gunu_mu(g) and g not in _FEDERAL[g.year]


def onceki_is_gunu(g: date) -> date:
    g -= timedelta(days=1)
    while not is_gunu_mu(g):
        g -= timedelta(days=1)
    return g


def is_gunleri(bas: date, son: date) -> List[date]:
    gunler = []
    g = bas
    while g <= son:
        if is_gunu_mu(g):
            gunler.append(g)
        g += timedelta(days=1)
    return gunler
