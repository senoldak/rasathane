import datetime

from capitolseeder.kanal.secim import ayin_ilk_cumasi, gunluk, haftalik
from tests.kanal.yardimci import beyan


def test_gunluk_uye_basi_ve_sira():
    y = [beyan(id=str(i), uye="A", tutar_alt=50001 + i) for i in range(5)]
    y += [beyan(id="b", uye="B", tutar_alt=1001)]
    s = gunluk(y)
    assert [b.uye for b in s].count("A") == 3 and s[-1].uye == "B" and s[0].tutar_alt == 50005


def test_gunluk_esitlikte_yeni_islem_once():
    eski = beyan(id="e", uye="E", islem_tarihi=datetime.date(2026, 9, 1))
    yeni = beyan(id="y", uye="Y", islem_tarihi=datetime.date(2026, 9, 9))
    assert [b.id for b in gunluk([eski, yeni])] == ["y", "e"]


def test_gunluk_adet():
    y = [beyan(id=str(i), uye=f"U{i}") for i in range(20)]
    assert len(gunluk(y)) == 8


def test_gunluk_hisse_disi_yok():
    assert gunluk([beyan(varlik_turu="GS")]) == []


def test_haftalik_uye_basina_sayar_ve_iki_parti():
    pzt = datetime.date(2026, 10, 19)
    b = [
        beyan(id=f"k{i}", uye="Khanna", parti="D", ticker="AAA", ilk_gorulme="2026-10-20")
        for i in range(30)
    ]
    b += [
        beyan(id="r", uye="Rep", parti="R", ticker="BBB", ilk_gorulme="2026-10-21"),
        beyan(id="d", uye="Dem", parti="D", ticker="BBB", ilk_gorulme="2026-10-21"),
        beyan(id="c", uye="X", ticker="CCC", ilk_gorulme="2026-10-22"),
        beyan(id="eski", uye="Y", ticker="DDD", ilk_gorulme="baslangic"),
        beyan(id="gelecek", uye="Z", ticker="EEE", ilk_gorulme="2026-10-26"),
    ]
    s = haftalik(b, pzt)
    assert s[0].ticker == "BBB" and s[0].iki_parti_alim and s[0].uye_sayisi == 2
    assert s[1].uye_sayisi == 1
    assert s[0].partiler == {"R": 1, "D": 1}
    tickerlar = [h.ticker for h in s]
    assert "DDD" not in tickerlar and "EEE" not in tickerlar


def test_haftalik_satis_iki_parti_alim_sayilmaz():
    pzt = datetime.date(2026, 10, 19)
    b = [
        beyan(id="r", uye="Rep", parti="R", ticker="BBB", islem="Sale (Full)", ilk_gorulme="2026-10-21"),
        beyan(id="d", uye="Dem", parti="D", ticker="BBB", ilk_gorulme="2026-10-21"),
        beyan(id="c", uye="X", ticker="CCC", ilk_gorulme="2026-10-22"),
        beyan(id="e", uye="Y", ticker="EEE", ilk_gorulme="2026-10-22"),
    ]
    bbb = haftalik(b, pzt)[0]
    assert bbb.ticker == "BBB" and not bbb.iki_parti_alim
    assert bbb.alan_uyeler == {"Dem"} and bbb.satan_uyeler == {"Rep"}


def test_haftalik_az_hisse_bos():
    assert haftalik([beyan(ilk_gorulme="2026-10-20")], datetime.date(2026, 10, 19)) == []


def test_ayin_ilk_cumasi():
    assert ayin_ilk_cumasi(datetime.date(2026, 11, 6))
    assert not ayin_ilk_cumasi(datetime.date(2026, 11, 13))
    assert not ayin_ilk_cumasi(datetime.date(2026, 11, 5))
