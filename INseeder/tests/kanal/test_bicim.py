from datetime import date

from inseeder.kanal.bicim import (
    fiyat,
    gun_adi,
    hafta_araligi,
    para,
    tarih_kisa,
    tarih_uzun,
    yuzde,
)
from inseeder.kanal.takvim import hafta_gunleri


def test_para():
    assert para(2_400_000) == "$2,40 Mn"
    assert para(910_400) == "$910 Bin"
    assert para(100_000) == "$100 Bin"
    assert para(1_200_000_000) == "$1,20 Mr"


def test_fiyat():
    assert fiyat(18.72) == "18,72"
    assert fiyat(1234.5) == "1.234,50"


def test_yuzde():
    assert yuzde(0.34) == "+34%"
    assert yuzde(25.0) == "+999%+"


def test_tarihler():
    assert tarih_uzun(date(2026, 10, 24)) == "24 Ekim 2026"
    assert tarih_kisa(date(2026, 10, 24)) == "24.10.2026"
    assert gun_adi(date(2026, 10, 23)) == "Cuma"


def test_hafta_araligi():
    assert hafta_araligi(hafta_gunleri(date(2026, 10, 23))) == "19–23 Ekim 2026"
    assert hafta_araligi(hafta_gunleri(date(2026, 10, 2))) == "28 Eylül – 2 Ekim 2026"
