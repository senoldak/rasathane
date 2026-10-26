"""ABD federal tatilleri (SEC kapalı günler) ve kanalın gün hesapları."""
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import List, Set
from zoneinfo import ZoneInfo


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Ayın n'inci (n=-1: son) belirli hafta günü. weekday: Pazartesi=0."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    next_month = date(year + month // 12, month % 12 + 1, 1)
    last = next_month - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(g: date) -> date:
    """Cumartesiye düşen sabit tatil Cuma, Pazara düşen Pazartesi gözlenir."""
    if g.weekday() == 5:
        return g - timedelta(days=1)
    if g.weekday() == 6:
        return g + timedelta(days=1)
    return g


@lru_cache(maxsize=None)
def _tatiller(year: int) -> Set[date]:
    sabit = [date(year, 1, 1), date(year, 6, 19), date(year, 7, 4),
             date(year, 11, 11), date(year, 12, 25)]
    gunler = {_observed(g) for g in sabit}
    # Bir sonraki yılın 1 Ocak'ı Cumartesiye düşerse 31 Aralık gözlenir.
    gunler.add(_observed(date(year + 1, 1, 1)))
    gunler.update({
        _nth_weekday(year, 1, 0, 3),    # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),    # Presidents' Day
        _nth_weekday(year, 5, 0, -1),   # Memorial Day
        _nth_weekday(year, 9, 0, 1),    # Labor Day
        _nth_weekday(year, 10, 0, 2),   # Columbus Day
        _nth_weekday(year, 11, 3, 4),   # Thanksgiving
    })
    return {g for g in gunler if g.year == year}


def federal_tatil_mi(g: date) -> bool:
    return g in _tatiller(g.year)


def is_gunu_mu(g: date) -> bool:
    return g.weekday() < 5 and not federal_tatil_mi(g)


def istanbul_bugun() -> date:
    return datetime.now(ZoneInfo("Europe/Istanbul")).date()


def anlatilan_gun(istanbul_bugun: date) -> date:
    """Bugünden önceki son hafta içi gün (tatil olsa bile)."""
    g = istanbul_bugun - timedelta(days=1)
    while g.weekday() >= 5:
        g -= timedelta(days=1)
    return g


def hafta_gunleri(g: date) -> List[date]:
    pazartesi = g - timedelta(days=g.weekday())
    return [pazartesi + timedelta(days=i) for i in range(5)]


def onceki_is_gunleri(g: date, n: int) -> List[date]:
    """g'den önceki n iş günü, eskiden yeniye."""
    sonuc: List[date] = []
    cur = g
    while len(sonuc) < n:
        cur -= timedelta(days=1)
        if is_gunu_mu(cur):
            sonuc.append(cur)
    return list(reversed(sonuc))
