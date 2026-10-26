from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

from rasathane_bist.bulten import pay_bulteni_csv_oku, pay_bulteni_oku

VERI = Path(__file__).parent / "veri"


def oku(ad: str) -> str:
    return (VERI / ad).read_text(encoding="ascii")


def test_pay_bulteni_oku_csv() -> None:
    gun, satirlar = pay_bulteni_csv_oku(oku("thb_ornek.csv"))
    assert gun == date(2026, 10, 23)
    assert len(satirlar) == 5
    v = {s.kod: s for s in satirlar}["AAIFO.V"]
    assert (v.tip, v.kapanis, v.en_iyi_alis, v.en_iyi_satis, v.hacim_tl, v.adet) == (
        "MSPOTECW",
        0.95,
        0.99,
        1.02,
        1590869.92,
        1485747,
    )
    assert (v.ad, v.onceki_kapanis, v.degisim_yuzde, v.aof, v.islem_sayisi) == (
        "XAUSQC3010264000.00IYM0000.01NA",
        1.41,
        -32.624,
        1.071,
        26,
    )


def test_hisse_satiri() -> None:
    _, satirlar = pay_bulteni_csv_oku(oku("thb_ornek.csv"))
    h = {s.kod: s for s in satirlar}["AAGYO.E"]
    assert h.tip == "MSPOTEQT"
    assert h.kapanis == 7.33
    assert h.adet == 5673504


def test_kapanisi_sifir_satir() -> None:
    _, satirlar = pay_bulteni_csv_oku(oku("thb_ornek.csv"))
    t = {s.kod: s for s in satirlar}["TBIQD.V"]
    assert t.kapanis == 0.0
    assert t.en_iyi_alis == 3.58


def test_pay_bulteni_zip() -> None:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("thb202610231.csv", oku("thb_ornek.csv"))
    gun, satirlar = pay_bulteni_oku(tampon.getvalue())
    assert gun == date(2026, 10, 23)
    assert len(satirlar) == 5


def test_pay_bulteni_karisik_tarih() -> None:
    metin = oku("thb_ornek.csv").replace("2026-10-23;AAGYO", "2026-10-22;AAGYO")
    with pytest.raises(ValueError):
        pay_bulteni_csv_oku(metin)
