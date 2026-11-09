import pytest
from opsi.viop import (
    BIST30_DAYANAK_ESLEMESI,
    MAKRO_DAYANAK_ESLEMESI,
    dayanak_to_yahoo,
    yahoo_to_dayanak,
    bs_fiyat,
    bs_delta,
    bs_teta_gunluk,
    etkin_kaldirac,
    ortuk_oynaklik,
)


def test_bist30_ve_makro_eslemeleri():
    assert dayanak_to_yahoo("THYAO") == "THYAO.IS"
    assert dayanak_to_yahoo("GARAN") == "GARAN.IS"
    assert dayanak_to_yahoo("XU030") == "XU030.IS"
    assert dayanak_to_yahoo("USDTRY") == "TRY=X"
    assert dayanak_to_yahoo("EURUSD") == "EURUSD=X"
    assert dayanak_to_yahoo("XAUUSD") == "GC=F"

    assert yahoo_to_dayanak("THYAO.IS") == "THYAO"
    assert yahoo_to_dayanak("GARAN.IS") == "GARAN"
    assert yahoo_to_dayanak("XU030.IS") == "XU030"
    assert yahoo_to_dayanak("TRY=X") == "USDTRY"
    assert yahoo_to_dayanak("EURUSD=X") == "EURUSD"
    assert yahoo_to_dayanak("GC=F") == "XAUUSD"


def test_bs_fiyat_put_call_parity():
    # Spot 100, Strike 100, T=1, r=0.05, vol=0.20
    S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
    call = bs_fiyat(S, K, T, r, sigma, "C")
    put = bs_fiyat(S, K, T, r, sigma, "P")

    # Put-Call Parity: C - P = S - K * exp(-r * T)
    import math
    assert math.isclose(call - put, S - K * math.exp(-r * T), rel_tol=1e-5)


def test_bs_delta_sinirlar():
    S, K, T, r, sigma = 100.0, 100.0, 0.5, 0.05, 0.25
    delta_c = bs_delta(S, K, T, r, sigma, "C")
    delta_p = bs_delta(S, K, T, r, sigma, "P")

    assert 0.0 < delta_c < 1.0
    assert -1.0 < delta_p < 0.0
    assert abs(delta_c - delta_p - 1.0) < 1e-5


def test_etkin_kaldirac():
    # Delta 0.5, spot 100, varant 5, çarpan 0.1
    kaldirac = etkin_kaldirac(0.5, 100.0, 5.0, 0.1)
    assert kaldirac == (0.5 * 100.0 * 0.1) / 5.0  # 1.0


def test_ortuk_oynaklik_tersine_cozum():
    S, K, T, r, sigma_gercek = 100.0, 105.0, 0.25, 0.40, 0.35
    fiyat = bs_fiyat(S, K, T, r, sigma_gercek, "C")
    iv = ortuk_oynaklik(fiyat, S, K, T, r, "C")
    assert iv is not None
    assert abs(iv - sigma_gercek) < 1e-4
