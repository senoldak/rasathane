from dataclasses import replace
from datetime import date, timedelta

from inseeder.kanal.grafik import grafik_karti, grafik_secimi
from inseeder.kanal.secim import Satir
from tests.kanal.yardimci import beyan

GUN = date(2026, 10, 23)


def _satir(sembol, tutar, ort_fiyat, unvan="Direktör"):
    return Satir(replace(beyan(sembol=sembol, tutar=tutar, unvan=unvan, sirket=f"{sembol} Inc"),
                         ort_fiyat=ort_fiyat), False, None)


def _fiyatlar(son=2.30, n=70):
    return [(GUN - timedelta(days=n - 1 - i), son + (i % 5) * 0.01) for i in range(n)]


def test_secim_en_buyuk_toplam():
    satirlar = [_satir("RENT", 2.25e6, 2.4), _satir("RENT", 1.63e6, 2.4), _satir("NXG", 439e3, 44.0)]
    assert grafik_secimi(satirlar, {"RENT": 2.30, "NXG": 43.95}.get) == "RENT"


def test_secim_sapma_atlar():
    satirlar = [_satir("RENT", 2.25e6, 3.55), _satir("RENT", 1.63e6, 3.55), _satir("NXG", 439e3, 43.95)]
    assert grafik_secimi(satirlar, {"RENT": 2.30, "NXG": 43.95}.get) == "NXG"


def test_secim_fiyat_yoksa_siradaki_ya_da_yok():
    satirlar = [_satir("RENT", 2.25e6, 2.3), _satir("NXG", 439e3, 43.95)]
    assert grafik_secimi(satirlar, {"NXG": 43.95}.get) == "NXG"
    assert grafik_secimi(satirlar, {}.get) is None


def test_grafik_karti_alanlari():
    satirlar = [_satir("RENT", 3e6, 2.0, "Direktör"), _satir("RENT", 1e6, 3.0, "%10 ortak"), _satir("NXG", 5e5, 40)]
    g = grafik_karti(GUN, "RENT", satirlar, _fiyatlar())
    assert g.fikir == "INseeder" and g.tarih == "23.10.2026"
    assert g.baslik == "RENT · RENT Inc"
    assert "Direktör" in g.alt_baslik and "%10 ortak" in g.alt_baslik and "$4,00 Mn" in g.alt_baslik
    assert g.yatay == 2.25  # tutar ağırlıklı ortalama alım fiyatı
    assert g.ozet[1][0] == "Alım fiyatı" and g.ozet[1][1].vurgu
    assert g.isaretler[0].gun == GUN and g.isaretler[0].etiket == "beyan 23.10"
    assert g.gunler[-1] == GUN and (GUN - g.gunler[0]).days <= 93
    assert g.kaynak == "SEC EDGAR · Yahoo Finance"
