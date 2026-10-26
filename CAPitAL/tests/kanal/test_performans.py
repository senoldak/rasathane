import datetime

import pandas as pd
import pytest

from capitolseeder.kanal import performans as perf
from capitolseeder.kanal.performans import FiyatHatasi, degisim, fiyatlari_cek, performans
from tests.kanal.yardimci import beyan

BUGUN = datetime.date(2026, 11, 6)
ISLEM = datetime.date(2026, 9, 1)


def _seri(baslangic_fiyat: float, son_fiyat: float):
    return [(ISLEM, baslangic_fiyat), (datetime.date(2026, 10, 1), (baslangic_fiyat + son_fiyat) / 2), (BUGUN, son_fiyat)]


def _alimlar(uye, ticker, n, parti="R", **kw):
    return [beyan(id=f"{uye}{ticker}{i}", uye=uye, parti=parti, ticker=ticker, islem_tarihi=ISLEM,
                  beyan_tarihi=datetime.date(2026, 9, 20), **kw) for i in range(n)]


FIYATLAR = {"SPY": _seri(100, 105), "UP": _seri(100, 120), "DN": _seri(100, 90)}


def test_degisim_tatil_sonraki_gun():
    f = [(datetime.date(2026, 9, 1), 100.0), (datetime.date(2026, 9, 3), 110.0), (datetime.date(2026, 10, 1), 121.0)]
    assert degisim(f, datetime.date(2026, 9, 2)) == pytest.approx(10.0)
    assert degisim(f, datetime.date(2026, 10, 2)) is None
    assert degisim([], datetime.date(2026, 9, 2)) is None


def test_performans_fark_ve_oran():
    b = _alimlar("A", "UP", 5) + _alimlar("B", "DN", 5, parti="D")
    ust, alt, bas = performans(b, FIYATLAR, BUGUN)
    assert ust[0].uye == "A" and ust[0].alim_sayisi == 5
    assert ust[0].ort_degisim == pytest.approx(20.0) and ust[0].ort_spy == pytest.approx(5.0)
    assert ust[0].fark == pytest.approx(15.0) and ust[0].spy_ustu_oran == pytest.approx(1.0)
    assert alt[0].uye == "B" and alt[0].fark == pytest.approx(-15.0) and alt[0].spy_ustu_oran == 0
    assert bas == datetime.date(2026, 9, 20)


def test_az_alim_ve_fiyatsiz_uye_elenir():
    b = _alimlar("A", "UP", 5) + _alimlar("B", "DN", 5) + _alimlar("Az", "UP", 4)
    b += _alimlar("F", "UP", 2) + _alimlar("F", "YOK", 4)
    ust, alt, _ = performans(b, FIYATLAR, BUGUN)
    adlar = {p.uye for p in ust + alt}
    assert adlar == {"A", "B"}


def test_satis_ve_hisse_disi_sayilmaz():
    b = _alimlar("A", "UP", 5) + _alimlar("B", "DN", 5)
    b += _alimlar("A", "DN", 5, islem="Sale (Full)") + _alimlar("A", "DN", 5, varlik_turu="GS")
    ust, _, _ = performans(b, FIYATLAR, BUGUN)
    assert ust[0].alim_sayisi == 5


def test_on_ikiden_az_uye_ikiye_bolunur():
    b = []
    for i, t in enumerate(["UP", "UP", "DN", "DN", "UP", "DN"]):
        b += _alimlar(f"U{i}", t, 5)
    ust, alt, _ = performans(b, FIYATLAR, BUGUN)
    assert len(ust) == 3 and len(alt) == 3 and not ({p.uye for p in ust} & {p.uye for p in alt})


def test_bir_yildan_eski_beyan_disarda():
    b = _alimlar("A", "UP", 5) + _alimlar("B", "DN", 5)
    eski = [beyan(id=f"e{i}", uye="E", ticker="UP", islem_tarihi=ISLEM, beyan_tarihi=datetime.date(2025, 9, 1))
            for i in range(5)]
    ust, alt, bas = performans(b + eski, FIYATLAR, BUGUN)
    assert "E" not in {p.uye for p in ust + alt} and bas == BUGUN - datetime.timedelta(days=365)


def test_spy_yoksa_hata():
    with pytest.raises(FiyatHatasi):
        performans(_alimlar("A", "UP", 5), {"UP": _seri(1, 2)}, BUGUN)


def test_uygun_uye_yoksa_hata():
    with pytest.raises(FiyatHatasi):
        performans(_alimlar("A", "UP", 2), FIYATLAR, BUGUN)


def test_yahoo_sembol_donusumu(monkeypatch):
    istenen = {}

    def sahte_indir(semboller, **kw):
        istenen["s"] = semboller
        tarihler = pd.to_datetime(["2026-09-01", "2026-09-02"])
        sutunlar = pd.MultiIndex.from_product([["BRK-B", "SPY", "BOS"], ["Close"]])
        veri = [[10.0, 100.0, float("nan")], [11.0, 101.0, float("nan")]]
        return pd.DataFrame(veri, index=tarihler, columns=sutunlar)

    monkeypatch.setattr(perf.yf, "download", sahte_indir)
    f = fiyatlari_cek(["BRK.B", "BOS"], datetime.date(2026, 9, 1))
    assert "BRK-B" in istenen["s"] and "SPY" in istenen["s"]
    assert f["BRK.B"] == [(datetime.date(2026, 9, 1), 10.0), (datetime.date(2026, 9, 2), 11.0)]
    assert "BOS" not in f and "SPY" in f


def test_kotasyonu_bitmis_hisse_disarda():
    eski_bitis = [(ISLEM, 100.0), (datetime.date(2026, 9, 15), 120.0)]  # bugünden çok önce bitiyor
    b = _alimlar("A", "UP", 5) + _alimlar("B", "DN", 5) + _alimlar("C", "BIT", 5)
    ust, alt, _ = performans(b, dict(FIYATLAR, BIT=eski_bitis), BUGUN)
    assert "C" not in {p.uye for p in ust + alt}


def test_gec_baslayan_seri_disarda():
    gec = [(datetime.date(2026, 10, 1), 100.0), (BUGUN, 130.0)]  # işlemden 30 gün sonra başlıyor
    b = _alimlar("A", "UP", 5) + _alimlar("B", "DN", 5) + _alimlar("C", "GEC", 5)
    ust, alt, _ = performans(b, dict(FIYATLAR, GEC=gec), BUGUN)
    assert "C" not in {p.uye for p in ust + alt}


def test_spy_ayni_bitis_tarihine_gore():
    spy = [(ISLEM, 100.0), (datetime.date(2026, 11, 3), 110.0), (BUGUN, 200.0)]
    hisse = [(ISLEM, 100.0), (datetime.date(2026, 11, 3), 120.0)]  # son kapanış 3 gün önce
    b = _alimlar("A", "H", 5) + _alimlar("B", "DN", 5)
    ust, _, _ = performans(b, dict(FIYATLAR, SPY=spy, H=hisse, DN=[(ISLEM, 100.0), (BUGUN, 90.0)]), BUGUN)
    a = next(p for p in ust if p.uye == "A")
    assert a.ort_spy == pytest.approx(10.0) and a.ort_degisim == pytest.approx(20.0)


def test_eksik_fiyat_orani_yuksekse_hata():
    b = _alimlar("A", "UP", 5) + _alimlar("B", "DN", 5) + _alimlar("C", "YOK", 5)
    with pytest.raises(FiyatHatasi):
        performans(b, FIYATLAR, BUGUN)
