import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx

from bioseeder.rasathane.ctgov import (
    Calisma, calismalari_cek, fark, goruntu_oku, goruntu_yaz, sorgu, yaklasanlar,
)
from bioseeder.rasathane.evren import Sirket
from bioseeder.rasathane.http import Istemci
from bioseeder.rasathane.olay import OlayTuru

ORN = Path(__file__).parent / "ornekler"
SPONSORLAR = {
    "biogen": Sirket("BIIB", 875045, "Biogen Inc.", "Nasdaq", 2836, 40000.0),
    "bristol myers squibb": Sirket("BMY", 14272, "Bristol-Myers Squibb Co", "NYSE", 2834, 90000.0),
}


def _istemci(sayfalar, istekler=None):
    sira = list(sayfalar)

    def isle(req):
        if istekler is not None:
            istekler.append(req)
        return httpx.Response(200, json=sira.pop(0))
    return Istemci(transport=httpx.MockTransport(isle), uyku=lambda s: None, sec_ua="biOF Rasathane test@ornek.com")


def _cek(sayfalar):
    eslesmeyen = set()
    return calismalari_cek(_istemci(sayfalar), sorgu(date(2026, 10, 23)), SPONSORLAR, eslesmeyen), eslesmeyen


def test_sorgu_filtresi():
    s = sorgu(date(2026, 10, 23))
    assert "AREA[LastUpdatePostDate]2026-10-23" in s["filter.advanced"]
    assert "AREA[LeadSponsorClass]INDUSTRY" in s["filter.advanced"]
    assert "LastUpdatePostDate" not in sorgu(None)["filter.advanced"]


def test_ayristirma():
    calismalar, _ = _cek([json.loads((ORN / "ctgov_sayfa.json").read_text())])
    c = {x.nct: x for x in calismalar}
    assert set(c) == {"NCT07221669", "NCT07293351"}  # Faz 1 ve eşleşmeyen sponsor dışarıda
    assert c["NCT07221669"].faz == "3" and c["NCT07221669"].ticker == "BIIB"
    assert c["NCT07293351"].faz == "2"
    assert c["NCT07293351"].bitis == "2027-03" and c["NCT07293351"].bitis_hassas == "AY"
    assert c["NCT07293351"].ilac == "Pumitamig"
    assert c["NCT07221669"].ilk_kayit == "2026-10-20"
    assert c["NCT07221669"].hastalik == "Muscular Atrophy, Spinal"


def test_sayfalama():
    tam = json.loads((ORN / "ctgov_sayfa.json").read_text())
    s1 = {"studies": tam["studies"][:1], "nextPageToken": "abc"}
    s2 = {"studies": tam["studies"][1:2]}
    istekler = []
    eslesmeyen = set()
    sonuc = calismalari_cek(_istemci([s1, s2], istekler), sorgu(None), SPONSORLAR, eslesmeyen)
    assert len(sonuc) == 2
    assert istekler[1].url.params["pageToken"] == "abc"


def test_eslesmeyen_sponsor():
    _, eslesmeyen = _cek([json.loads((ORN / "ctgov_sayfa.json").read_text())])
    assert eslesmeyen == {"Privately Held Bio GmbH"}


def _c(**kw):
    temel = dict(nct="NCT1", ticker="AAA", faz="3", durum="RECRUITING", bitis="2027-01-15",
                 bitis_hassas="GUN", sonuc=False, ilac="Ilac", hastalik="Hastalik")
    temel.update(kw)
    return Calisma(**temel)


G = date(2026, 10, 23)


def _turler(eski, yeni):
    return [o.tur for o in fark({c.nct: c for c in eski}, yeni, G, {"AAA": True})]


def test_fark_kurallari():
    assert _turler([], [_c(ilk_kayit="2026-10-23")]) == [OlayTuru.YENI_FAZ3]
    assert _turler([], [_c(faz="2", ilk_kayit="2026-10-23")]) == [OlayTuru.YENI_FAZ2]
    assert _turler([], [_c(ilk_kayit="2021-05-01")]) == []  # eski çalışma görüntüye sessizce girer
    assert _turler([_c()], [_c(durum="TERMINATED")]) == [OlayTuru.DURDURULDU]
    assert _turler([_c(durum="TERMINATED")], [_c(durum="WITHDRAWN")]) == []
    assert _turler([_c()], [_c(durum="COMPLETED")]) == [OlayTuru.TAMAMLANDI]
    assert _turler([_c()], [_c(sonuc=True)]) == [OlayTuru.SONUC_GIRILDI]
    assert _turler([_c()], [_c(bitis="2027-03", bitis_hassas="AY")]) == [OlayTuru.TARIH_KAYDI]
    assert _turler([_c()], [_c(bitis="2027-02-04")]) == []  # 20 gün kayma
    assert _turler([_c()], [_c()]) == []


def test_fark_ayrintilari():
    o = fark({"NCT1": _c(faz="2/3")}, [_c(faz="2/3", durum="SUSPENDED")], G, {"AAA": True})[0]
    assert o.faz3 and o.etiket_ek == "FAZ 2/3" and o.mikro
    assert o.kimlik == "NCT1:DURDURULDU:2026-10-23"
    assert o.satir == "Ilac · Hastalik"
    assert o.baglanti == "https://clinicaltrials.gov/study/NCT1"
    k = fark({"NCT1": _c()}, [_c(bitis="2027-03", bitis_hassas="AY")], G, {})[0]
    assert k.ayrinti == "Bitiş 01.2027 → 03.2027"


def test_goruntu_yaz_oku(tmp_path):
    d = {"NCT2": _c(nct="NCT2"), "NCT1": _c(ilac="A, B")}
    goruntu_yaz(d, tmp_path / "g.csv")
    assert goruntu_oku(tmp_path / "g.csv") == d
    assert goruntu_oku(tmp_path / "yok.csv") == {}


def test_yaklasanlar():
    bugun = date(2026, 10, 25)
    g = {c.nct: c for c in [
        _c(nct="A", faz="2", bitis="2026-11-01"),
        _c(nct="B", faz="3", bitis="2026-12-10"),
        _c(nct="C", faz="3", bitis="2027-01-10"),  # 77 gün
        _c(nct="D", faz="3", bitis="2026-11-05", durum="COMPLETED"),
        _c(nct="E", faz="2/3", bitis="2026-11", bitis_hassas="AY"),
    ]}
    assert [c.nct for c in yaklasanlar(g, bugun)] == ["E", "B", "A"]
