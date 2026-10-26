from datetime import date

import pytest

from inseeder.kanal.takvim import (
    anlatilan_gun,
    federal_tatil_mi,
    hafta_gunleri,
    is_gunu_mu,
    onceki_is_gunleri,
)


@pytest.mark.parametrize("g", [
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 5, 25),
    date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 10, 12),
    date(2026, 11, 11), date(2026, 11, 26), date(2026, 12, 25), date(2027, 1, 1),
])
def test_federal_holidays(g):
    assert federal_tatil_mi(g) is True


@pytest.mark.parametrize("g", [date(2026, 10, 23), date(2026, 7, 6), date(2026, 11, 27)])
def test_not_holidays(g):
    assert federal_tatil_mi(g) is False


def test_sunday_holiday_moves_to_monday():
    # 4 Temmuz 2027 Pazar => 5 Temmuz Pazartesi
    assert federal_tatil_mi(date(2027, 7, 5)) is True


def test_is_gunu():
    assert is_gunu_mu(date(2026, 10, 23)) is True
    assert is_gunu_mu(date(2026, 10, 24)) is False
    assert is_gunu_mu(date(2026, 10, 12)) is False


def test_anlatilan_gun():
    assert anlatilan_gun(date(2026, 10, 27)) == date(2026, 10, 26)  # Salı -> Pazartesi
    assert anlatilan_gun(date(2026, 10, 31)) == date(2026, 10, 30)  # Cumartesi -> Cuma
    assert anlatilan_gun(date(2026, 10, 26)) == date(2026, 10, 23)  # Pazartesi -> Cuma
    assert anlatilan_gun(date(2026, 12, 26)) == date(2026, 12, 25)  # tatil kontrolü yok


def test_hafta_gunleri():
    gunler = hafta_gunleri(date(2026, 10, 23))
    assert gunler[0] == date(2026, 10, 19)
    assert gunler[-1] == date(2026, 10, 23)
    assert len(gunler) == 5


def test_onceki_is_gunleri_skips_holiday():
    assert onceki_is_gunleri(date(2026, 10, 14), 2) == [date(2026, 10, 9), date(2026, 10, 13)]
