from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from rasathane_bist.viop import (
    OpsiyonSarti,
    ViopSatiri,
    opsiyon_kodu_coz,
    opsiyon_mu,
    vadeli_mi,
    viop_bulteni_oku,
    viop_bulteni_url,
)

VERI = Path(__file__).parent / "veri"


def oku_bayt(ad: str) -> bytes:
    return (VERI / ad).read_bytes()


def satirlar() -> dict[str, ViopSatiri]:
    _, s = viop_bulteni_oku(oku_bayt("viop_ornek.csv"))
    return {x.kod: x for x in s}


def test_viop_bulteni_url() -> None:
    assert (
        viop_bulteni_url(date(2026, 10, 23))
        == "https://borsaistanbul.com/viopdata/viop_20261023.csv"
    )


def test_viop_bulteni_oku_vadeli() -> None:
    gun, tum = viop_bulteni_oku(oku_bayt("viop_ornek.csv"))
    assert gun == date(2026, 10, 23)
    assert len(tum) == 13
    t = satirlar()["F_THYAO1026"]
    assert (
        t.dayanak,
        t.vade,
        t.uzlasma,
        t.onceki_uzlasma,
        t.acik_pozisyon,
        t.acik_pozisyon_degisimi,
    ) == ("THYAO.E", date(2026, 10, 30), 259.7, 260.65, 249190, -45695)
    assert (t.pazar, t.segment, t.tip, t.sinif) == ("D_EQ", "SSF", "D_EQ_FPD", "DE_THYAO_FPD")
    assert (t.uzlasma_degisim_yuzde, t.kapanis, t.hacim_tl, t.prim_hacmi) == (
        -0.36,
        260.4,
        4352853385.0,
        0.0,
    )
    assert (t.lot, t.islem_sayisi, t.ad) == (170138, 36354, "THYAO_10/2026_VIS")


def test_vadeli_ve_opsiyon_ayrimi() -> None:
    s = satirlar()
    for kod in ("F_XU0301026", "F_USDTRY1026", "F_EURUSD1026", "F_ELCBAS0127", "F_XAUTRYM1026"):
        assert vadeli_mi(s[kod]) and not opsiyon_mu(s[kod])
    for kod in ("O_XU030E1026C14000.00", "O_AKBNKE1026C64.00", "O_USDTRYKE1026C49000"):
        assert opsiyon_mu(s[kod]) and not vadeli_mi(s[kod])


def test_opsiyon_satiri_alanlari() -> None:
    s = satirlar()
    p = s["O_XU030E1026P14000.00"]
    assert (p.segment, p.dayanak, p.vade, p.uzlasma, p.prim_hacmi) == (
        "INO",
        "D_XU030D",
        date(2026, 10, 30),
        222.33,
        3539362.4,
    )
    assert opsiyon_kodu_coz(p.kod) == OpsiyonSarti("XU030", "P", 14000.0, "E")


def test_uzlasmasi_olmayan_satir() -> None:
    o = satirlar()["O_AKBNKE1026C64.00"]
    assert o.onceki_uzlasma == 0.0  # boş sayı 0
    s = satirlar()["F_ELCBAS0127"]
    assert (s.hacim_tl, s.lot, s.islem_sayisi, s.acik_pozisyon) == (0.0, 0, 0, 0)


@pytest.mark.parametrize(
    "kod,beklenen",
    [
        ("O_XU030E0227C15000.00", ("XU030", "C", 15000.0, "E")),
        ("O_XU030E1026P14000.00", ("XU030", "P", 14000.0, "E")),
        ("O_AKBNKE1026C64.00", ("AKBNK", "C", 64.0, "E")),
        ("O_TOASOE1026P172.50", ("TOASO", "P", 172.5, "E")),
        ("O_THYAOA1226C300.00", ("THYAO", "C", 300.0, "A")),
        ("O_USDTRYKE1026C49000", ("USDTRYK", "C", 49.0, "E")),
        ("O_USDTRYKE1026P46500", ("USDTRYK", "P", 46.5, "E")),
        ("O_P_USDTRYKE1126C51000", ("USDTRYK", "C", 51.0, "E")),
        ("TM_O_AKBNKE301026C71.00", ("AKBNK", "C", 71.0, "E")),
    ],
)
def test_opsiyon_kodu_coz(kod: str, beklenen: tuple[str, str, float, str]) -> None:
    assert opsiyon_kodu_coz(kod) == OpsiyonSarti(*beklenen)


@pytest.mark.parametrize("kod", ["F_THYAO1026", "", "O_", "O_AKBNKE1026X64.00", "XU030E1026C1.00"])
def test_opsiyon_kodu_bozuk(kod: str) -> None:
    assert opsiyon_kodu_coz(kod) is None


def test_karisik_tarih_valueerror() -> None:
    metin = oku_bayt("viop_ornek.csv").decode("ascii").splitlines()
    metin[3] = metin[3].replace("2026-10-23", "2026-10-22", 1)
    with pytest.raises(ValueError, match="tek tarih"):
        viop_bulteni_oku("\n".join(metin).encode("ascii"))


def test_eksik_sutun_valueerror() -> None:
    metin = oku_bayt("viop_ornek.csv").decode("ascii").replace("ONCEKI UZLASMA FIYATI", "X", 1)
    with pytest.raises(ValueError, match="bültende sütun yok: ONCEKI UZLASMA FIYATI"):
        viop_bulteni_oku(metin.encode("ascii"))
