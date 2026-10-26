from datetime import date, timedelta

import pytest

from bioseeder.rasathane.grafik import olay_grafigi
from bioseeder.rasathane.olay import Olay, OlayTuru

G = date(2026, 10, 23)


def _fiyat(bitis=G, n=120):
    return [(bitis - timedelta(days=n - 1 - i), 10.0 + i * 0.1) for i in range(n)]


def _olay(baglanti="https://www.sec.gov/x", tur=OlayTuru.FAZ3_SONUC):
    return Olay(kimlik="a", tur=tur, ticker="CLYM", satir="Ilac · Hastalik", ayrinti="", tarih=G, faz3=True,
                baglanti=baglanti)


def test_grafik_alanlari():
    g = olay_grafigi(_olay(), "Climb Bio", "23.10.2026", _fiyat())
    assert (g.fikir, g.tarih, g.baslik) == ("biOF", "23.10.2026", "CLYM · Climb Bio")
    assert g.alt_baslik == "FAZ 3 SONUÇ · SEC 8-K, 23.10.2026"
    assert [i.etiket for i in g.isaretler] == ["FAZ 3 SONUÇ"] and g.isaretler[0].gun == G
    assert g.ozet[1][0] == "Olay günü" and g.ozet[1][1].vurgu
    assert g.ozet[0][1].metin == "$21,80" and g.ozet[1][1].metin == "$21,90"
    assert g.kaynak == "SEC EDGAR · Yahoo Finance"
    assert g.gunler[-1] == G and (G - g.gunler[0]).days <= 93


def test_ctgov_olayi_kaynagi():
    g = olay_grafigi(_olay(baglanti="https://clinicaltrials.gov/study/NCT01234567"), "", "23.10.2026", _fiyat())
    assert g.baslik == "CLYM"
    assert g.alt_baslik.endswith("ClinicalTrials.gov, 23.10.2026")
    assert g.kaynak == "ClinicalTrials.gov · Yahoo Finance"


def test_olay_gunu_seride_yoksa_hata():
    with pytest.raises(ValueError):
        olay_grafigi(_olay(), "Climb Bio", "23.10.2026", _fiyat(bitis=G - timedelta(days=1)))
