from __future__ import annotations

from datetime import date

import pytest

from rasathane_bist.varant_adi import VARANT_TIPLERI, varant_adi_coz


@pytest.mark.parametrize(
    "ad,beklenen",
    [
        (
            "XAUSQC3010264000.00IYM0000.01NA",
            ("XAUSQ", "C", date(2026, 10, 30), 4000.0, "IYM", 0.01),
        ),
        ("THYAOP3010260380.00IYM0000.03NA", ("THYAO", "P", date(2026, 10, 30), 380.0, "IYM", 0.03)),
        (
            "XU030C30102621500.0AKM000.001NA",
            ("XU030", "C", date(2026, 10, 30), 21500.0, "AKM", 0.001),
        ),
        (
            "DAXC30102630000.0AKM0.00002NA",
            ("DAX", "C", date(2026, 10, 30), 30000.0, "AKM", 0.00002),
        ),
        ("USDC3010260054.00IYF00000.5NA", ("USD", "C", date(2026, 10, 30), 54.0, "IYF", 0.5)),
        # gerçek dosyadaki 0000001 (noktasız) çarpan örneği
        ("USDC3010260049.00TGB0000001NA", ("USD", "C", date(2026, 10, 30), 49.0, "TGB", 1.0)),
    ],
)
def test_varant_adi_coz(ad: str, beklenen: tuple[object, ...]) -> None:
    s = varant_adi_coz(ad)
    assert s is not None
    assert (s.dayanak, s.tur, s.vade, s.kullanim, s.ihracci, s.carpan) == beklenen


@pytest.mark.parametrize("ad", ["AGAOGLU GMYO", "", "THYAOX3010260380.00IYM0000.03NA"])
def test_varant_adi_bozuk(ad: str) -> None:
    assert varant_adi_coz(ad) is None


def test_varant_adi_gecersiz_tarih() -> None:
    assert varant_adi_coz("THYAOP3113260380.00IYM0000.03NA") is None


def test_varant_tipleri() -> None:
    assert VARANT_TIPLERI == {"MSPOTECW": "C", "MSPOTEPW": "P"}
