"""Kanal kart çizimi: PNG boyutu, Türkçe karakterler, kısaltma."""

import io

from PIL import Image
from rasathane_ortak import kagit

from opsi.kanal.cizim import SAYFA_SATIRI, csp_ciz, prim_ciz, sarsinti_ciz, tarih_tr
from opsi.kanal.kartlar import CspKarti, PrimKarti, SarsintiSatiri


def _s(sembol: str, degisim: float, bilanco: bool = False) -> SarsintiSatiri:
    return {
        "sembol": sembol,
        "ad": "Energy Select Sector SPDR Fund Çok Uzun İsim",
        "kapanis": 66.56,
        "fiyat_degisim": -0.0158,
        "iv_once": 0.27,
        "iv_simdi": 0.27 * (1 + degisim),
        "iv_degisim": degisim,
        "bilanco": bilanco,
    }


ORNEK_S = [
    _s(f"S{i}", d, i == 0) for i, d in enumerate([-0.7, -0.2, -0.1, -0.05, 0.3, 0.2, 0.1, 0.05])
]
ORNEK_P: PrimKarti = {
    "satirlar": [
        {"sembol": f"P{i}", "ad": "Şirket Ğİ", "kapanis": 68.69, "skew": 1.6 - i / 20, "fark": 0.5}
        for i in range(6)
    ],
    "medyan": 1.1,
    "tum_skewler": [1.0 + i / 200 for i in range(180)],
}
ORNEK_C: CspKarti = {
    "bant": "$5k–15k",
    "iv_etiket": "IV yüzd. (23.10'dan beri)",
    "satirlar": [
        {
            "sembol": f"C{i}",
            "ad": "Uber Technologies",
            "fiyat": 67.62,
            "hareket_yuzde": 0.121,
            "hareket_alt": 59.46,
            "hareket_ust": 75.78,
            "iv30": 0.421,
            "iv_konum": None if i == 4 else 0.68,
            "skor": 76.0,
        }
        for i in range(5)
    ],
}


def test_kartlar_tek_sayfa_1080_genislikte_png() -> None:
    kartlar = (
        sarsinti_ciz(ORNEK_S, "2026-10-23", "2026-10-22", 185),
        prim_ciz(ORNEK_P, "2026-10-23", 185),
        csp_ciz(ORNEK_C, "2026-10-23", "26–30 Eki"),
    )
    for k in kartlar:
        sayfalar = kagit.ciz(k, sayfa_basina=SAYFA_SATIRI)
        assert len(sayfalar) == 1
        im = Image.open(io.BytesIO(sayfalar[0].png))
        assert im.format == "PNG" and im.width == 1080


def test_sarsinti_karti() -> None:
    k = sarsinti_ciz(ORNEK_S, "2026-10-23", "2026-10-22", 185)
    assert (k.fikir, k.ad, k.tarih, k.kaynak) == (
        "OPsi",
        "IV Sarsıntısı",
        "23.10.2026",
        "Yahoo Finance",
    )
    assert k.sutunlar == ("Hisse", "Kapanış", "IV30", "Değişim")
    assert "185 sembol" in k.alt_baslik
    ilk = k.satirlar[0]
    assert ilk.etiket == "bilanço" and k.satirlar[1].etiket == ""
    assert ilk.sag[0].alt == "−%1,58"
    assert ilk.sag[1].metin == "27→8"
    assert ilk.sag[2].metin == "−%70" and ilk.sag[2].vurgu and ilk.sag[2].kalin


def test_prim_karti() -> None:
    k = prim_ciz(ORNEK_P, "2026-10-23", 185)
    assert k.ad == "Aşağı Yön Primi"
    assert k.alt_baslik == "Put satıcısının en çok prim aldığı hisseler · 185 sembol, ortanca 1,10"
    assert k.sutunlar == ("Hisse", "Kapanış", "Skew")
    assert k.satirlar[0].sag[1].metin == "1,60" and k.satirlar[0].sag[1].vurgu


def test_csp_karti() -> None:
    k = csp_ciz(ORNEK_C, "2026-10-23", "26–30 Eki")
    assert k.ad == "Nakit Teminatlı Put · $5k–15k"
    assert k.alt_baslik == "26–30 Eki haftası · 20–45 gün · IV yüzd. (23.10'dan beri)"
    assert k.sutunlar == ("Hisse", "Fiyat", "Beklenen hareket", "IV30", "Puan")
    s = k.satirlar[0]
    assert s.sag[1].metin == "±%12,1" and s.sag[1].alt == "$59,46 – $75,78"
    assert s.sag[2].metin == "42,1" and s.sag[2].alt == "konum %68"
    assert k.satirlar[4].sag[2].alt == "konum —"
    assert s.sag[3].metin == "76" and s.sag[3].vurgu


def test_tarih_tr() -> None:
    assert tarih_tr("2026-08-03") == "3 Ağu 2026"
    assert tarih_tr("2026-10-23") == "23 Eki 2026"
