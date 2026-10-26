from __future__ import annotations

import pytest

from rasathane_bist.opsiyon import (
    bs_delta,
    bs_fiyat,
    bs_teta_gunluk,
    etkin_kaldirac,
    ortuk_oynaklik,
)


def test_bs_bilinen_degerler() -> None:
    assert bs_fiyat(100, 100, 1, 0.05, 0.2, "C") == pytest.approx(10.4506, abs=1e-4)
    assert bs_fiyat(100, 100, 1, 0.05, 0.2, "P") == pytest.approx(5.5735, abs=1e-4)
    assert bs_delta(100, 100, 1, 0.05, 0.2, "C") == pytest.approx(0.6368, abs=1e-4)
    assert bs_delta(100, 100, 1, 0.05, 0.2, "P") == pytest.approx(-0.3632, abs=1e-4)
    assert bs_teta_gunluk(100, 100, 1, 0.05, 0.2, "C") < 0


def test_bs_vadesi_gelmis_ic_deger() -> None:
    assert bs_fiyat(120, 100, 0, 0.05, 0.2, "C") == pytest.approx(20.0)
    assert bs_fiyat(120, 100, 0, 0.05, 0.2, "P") == 0.0


def test_ortuk_oynaklik_geri_cozer() -> None:
    f = bs_fiyat(100, 110, 0.25, 0.4, 0.37, "C")
    assert ortuk_oynaklik(f, 100, 110, 0.25, 0.4, "C") == pytest.approx(0.37, abs=1e-4)


def test_ortuk_oynaklik_satim_geri_cozer() -> None:
    f = bs_fiyat(100, 110, 0.25, 0.4, 0.37, "P")
    assert ortuk_oynaklik(f, 100, 110, 0.25, 0.4, "P") == pytest.approx(0.37, abs=1e-4)


def test_ortuk_oynaklik_ic_degerin_alti_none() -> None:
    assert ortuk_oynaklik(1.0, 120, 100, 0.5, 0.0, "C") is None


def test_ortuk_oynaklik_ust_sinirin_ustu_none() -> None:
    assert ortuk_oynaklik(150.0, 100, 100, 0.5, 0.0, "C") is None


def test_etkin_kaldirac() -> None:
    assert etkin_kaldirac(0.5, 300, 1.5, 0.03) == pytest.approx(3.0)
    assert etkin_kaldirac(-0.5, 300, 1.5, 0.03, kur=2.0) == pytest.approx(6.0)
