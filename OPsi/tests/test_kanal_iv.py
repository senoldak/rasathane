"""Kanal IV hesapları: Black-Scholes ile fiyatlanmış sahte zincirler, ağ yok."""

import math

import pytest
from kanal_yardim import NOW, kontrat, zincir_bs

from opsi.kanal.iv import atm_iv, beklenen_hareket, gecerli_noktalar, iv30, skew25


def test_iv30_ara_degeri_toplam_varyansla() -> None:
    n = gecerli_noktalar(zincir_bs({23: 0.40, 37: 0.50}), 100, now=NOW)
    beklenen = math.sqrt(
        (0.40**2 * 23 + (0.50**2 * 37 - 0.40**2 * 23) * (30 - 23) / (37 - 23)) / 30
    )
    assert iv30(n, 100) == pytest.approx(beklenen, abs=0.005)


def test_iv30_tek_vade_20_45_icinde() -> None:
    n = gecerli_noktalar(zincir_bs({33: 0.42}), 100, now=NOW)
    assert iv30(n, 100) == pytest.approx(0.42, abs=0.005)


def test_iv30_uygun_vade_yoksa_none() -> None:
    n = gecerli_noktalar(zincir_bs({60: 0.42}), 100, now=NOW)
    assert iv30(n, 100) is None


def test_iv_bulunamayan_kontrat_sahte_030_vermez() -> None:
    c = kontrat(bid=0.0, ask=0.0, lastPrice=0.0, volume=0)
    assert gecerli_noktalar([c], 100, now=NOW) == []


def test_islem_gormemis_son_fiyat_kullanilmaz() -> None:
    c = kontrat(bid=0.0, ask=0.0, lastPrice=2.0, volume=0)
    assert gecerli_noktalar([c], 100, now=NOW) == []


def test_atm_uzaksa_none() -> None:
    n = gecerli_noktalar(zincir_bs({30: 0.40}), 100, now=NOW)
    uzak = [x for x in n if abs(x["strike"] / 100 - 1) > 0.05]
    assert atm_iv(uzak, uzak[0]["expiry"], 100) is None


def test_skew25_oran() -> None:
    n = gecerli_noktalar(zincir_bs({30: 0.40}, put25_iv=0.48), 100, now=NOW)
    assert skew25(n, 100) == pytest.approx(1.20, abs=0.02)


def test_skew25_delta_yoksa_none() -> None:
    n = gecerli_noktalar(zincir_bs({30: 0.40}, sadece_atm=True), 100, now=NOW)
    assert skew25(n, 100) is None


def test_beklenen_hareket() -> None:
    y, a, u = beklenen_hareket(100.0, 0.40, 30)
    assert y == pytest.approx(0.40 * math.sqrt(30 / 365))
    assert (a, u) == pytest.approx((100 * (1 - y), 100 * (1 + y)))


def test_genis_alis_satis_makasi_atlanir() -> None:
    c = kontrat(bid=0.05, ask=3.00, lastPrice=0.0, volume=0, openInterest=500)
    assert gecerli_noktalar([c], 100, now=NOW) == []


def test_dusuk_hacim_ve_oi_atlanir() -> None:
    c = kontrat(volume=2, openInterest=3)
    assert gecerli_noktalar([c], 100, now=NOW) == []
