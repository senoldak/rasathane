from datetime import date

from bioseeder.rasathane.ctgov import Calisma
from bioseeder.rasathane.kart import Kutucuk, calisma_kutucugu, kart, kutucuk_satiri, olay_kutucugu
from bioseeder.rasathane.olay import KIRMIZI, Olay, OlayTuru
from rasathane_ortak import kagit


def _k(i=0, renk="#00e5ff"):
    return Kutucuk(ticker=f"T{i}", etiket="YENİ FAZ 2", renk=renk, satir="İlaç · Hastalık", ayrinti="Ayrıntı",
                   mikro=i % 2 == 0)


def test_kutucuk_satiri():
    s = kutucuk_satiri(_k(0))
    assert (s.ust, s.etiket, s.alt) == ("T0", "YENİ FAZ 2", "İlaç · Hastalık · mikro")
    assert s.sag[0].metin == "Ayrıntı" and s.sag[0].ikincil and not s.sag[0].vurgu
    assert kutucuk_satiri(_k(1)).alt == "İlaç · Hastalık"


def test_kart_ve_sayfalar():
    k = kart("Sabah Bülteni", "23.10.2026", [_k(i) for i in range(13)], "Günün faz ve FDA değişiklikleri")
    assert (k.fikir, k.ad, k.tarih, k.kaynak) == ("biOF", "Sabah Bülteni", "23.10.2026",
                                                  "ClinicalTrials.gov · SEC EDGAR")
    sayfalar = kagit.ciz(k, sayfa_basina=6)
    assert [s.satirlar for s in sayfalar] == [tuple(range(6)), tuple(range(6, 12)), (12,)]


def test_olay_kutucugu():
    o = Olay(kimlik="x", tur=OlayTuru.DURDURULDU, ticker="IOVA", satir="Lifileucel · Melanoma",
             ayrinti="Durum: RECRUITING → TERMINATED", tarih=date(2026, 10, 23), faz3=True, mikro=True,
             etiket_ek="FAZ 2/3")
    k = olay_kutucugu(o)
    assert (k.ticker, k.etiket, k.renk, k.mikro) == ("IOVA", "FAZ 2/3", KIRMIZI, True)


def _c(**kw):
    t = dict(nct="N", ticker="APTO", faz="2", durum="RECRUITING", bitis="2026-11", bitis_hassas="AY",
             sonuc=False, ilac="Tuspetinib", hastalik="AML")
    t.update(kw)
    return Calisma(**t)


def test_calisma_kutucugu():
    k = calisma_kutucugu(_c(), date(2026, 10, 25), 4.5, mikro=False)
    assert k.etiket == "11.2026"
    assert k.ayrinti == "SEYRELTME RİSKİ · 4,5 ay" and k.ayrinti_renk == KIRMIZI
    assert kutucuk_satiri(k).sag[0].vurgu  # seyreltme riski tek vurgu rengiyle işaretlenir
    k2 = calisma_kutucugu(_c(bitis="2026-11-04", bitis_hassas="GUN", faz="3"), date(2026, 10, 25), 31.0, mikro=False)
    assert k2.etiket == "10 GÜN" and k2.ayrinti == "Nakit pisti 31 ay" and k2.ayrinti_renk is None
    assert "Faz 3" in k2.satir
    assert calisma_kutucugu(_c(), date(2026, 10, 25), None, mikro=True).ayrinti == "Nakit pisti: —"
