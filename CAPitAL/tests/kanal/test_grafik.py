import datetime

from capitolseeder.kanal.grafik import gecikme_grafigi, gecikme_secimi
from tests.kanal.yardimci import beyan

BUGUN = datetime.date(2026, 10, 22)


def _seri(bas, n, deger=100.0, adim=1.0):
    return [(bas + datetime.timedelta(days=i), deger + i * adim) for i in range(n)]


def test_secim_en_buyuk_ust_sinir():
    buyuk = beyan(id="a", ticker="BIG", tutar_alt=15001, tutar_ust=50000)
    kucuk = beyan(id="b", ticker="SML", tutar_alt=1001, tutar_ust=15000)
    assert gecikme_secimi([kucuk, buyuk]).ticker == "BIG"


def test_secim_hisse_olmayan_ve_satis_atlanir():
    satis = beyan(id="s", ticker="SEL", islem="Sale", tutar_ust=1_000_000)
    tahvil = beyan(id="t", ticker="", varlik_turu="GS", tutar_ust=5_000_000)
    alis = beyan(id="a", ticker="BUY", tutar_ust=15000)
    assert gecikme_secimi([satis, tahvil, alis]).ticker == "BUY"
    assert gecikme_secimi([satis]) is None


def test_secim_esitlikte_gecikme():
    a = beyan(id="a", ticker="AAA", tutar_alt=1001, tutar_ust=15000, gecikme=13)
    b = beyan(id="b", ticker="BBB", tutar_alt=1001, tutar_ust=15000, gecikme=21)
    assert gecikme_secimi([a, b]).ticker == "BBB"


def test_grafik_alanlari_ve_spy_olcegi():
    b = beyan(ticker="NVDA", varlik="NVIDIA Corporation", uye="Cleo Fields", parti="D", eyalet="LA",
              tutar_alt=1001, tutar_ust=15000, islem_tarihi=datetime.date(2026, 10, 1),
              beyan_tarihi=BUGUN, gecikme=21)
    kapanis = _seri(datetime.date(2026, 7, 1), 115, 100.0, 1.0)
    spy = _seri(datetime.date(2026, 7, 1), 115, 500.0, 2.0)
    g = gecikme_grafigi(b, BUGUN, kapanis, spy)
    assert g.fikir == "CAPitAL" and g.tarih == "22.10.2026"
    assert g.baslik == "NVDA · NVIDIA"
    assert g.alt_baslik == "C. Fields (D-LA) · Alış $1k–15k · işlemden 21 gün sonra beyan"
    assert [i.etiket for i in g.isaretler] == ["işlem 01.10", "beyan 22.10"]
    assert g.golge == (datetime.date(2026, 10, 1), BUGUN)
    assert g.karsilastirma[0] == g.seri[0]
    assert g.karsilastirma_adi == "S&P 500"
    assert g.ozet[1][1].vurgu and g.ozet[0][0] == "İşlem günü"
    assert g.gunler[-1] == BUGUN and (BUGUN - g.gunler[0]).days <= 93
    assert g.kaynak == "House Clerk · Yahoo Finance"
    assert gecikme_grafigi(replace_meclis(b), BUGUN, kapanis, spy).kaynak == "Senate eFD · Yahoo Finance"


def replace_meclis(b):
    from dataclasses import replace
    return replace(b, meclis="Senato")


def test_tatil_gunu_en_yakin_isleme_kayar():
    b = beyan(islem_tarihi=datetime.date(2026, 10, 3), beyan_tarihi=datetime.date(2026, 10, 25), gecikme=22)
    hafta_ici = [(g, v) for g, v in _seri(datetime.date(2026, 7, 1), 116) if g.weekday() < 5]
    g = gecikme_grafigi(b, datetime.date(2026, 10, 25), hafta_ici, hafta_ici)
    assert [i.gun for i in g.isaretler] == [datetime.date(2026, 10, 5), datetime.date(2026, 10, 23)]
