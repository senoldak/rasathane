import datetime
import io

from PIL import Image

from capitolseeder.kanal import kart
from capitolseeder.kanal.kart import gunluk_karti, haftalik_karti, performans_karti
from capitolseeder.kanal.performans import UyePerformansi
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Kart
from capitolseeder.kanal.secim import HisseOzeti
from tests.kanal.yardimci import beyan

TARIH = datetime.date(2026, 10, 24)


def _cizilir(k: Kart) -> None:
    for s in kagit.ciz(k):
        im = Image.open(io.BytesIO(s.png))
        assert im.format == "PNG" and im.width == 1080


def test_gunluk_kart():
    secilen = [beyan(id=str(i), gec=i % 2 == 0, gecikme=56) for i in range(8)]
    k = gunluk_karti(secilen, TARIH, 4, 66)
    assert (k.fikir, k.ad, k.tarih, k.kaynak) == ("CAPitAL", "Günün Kongre Beyanları", "24.10.2026",
                                                  "House Clerk / Senate eFD")
    assert len(k.satirlar) == 6
    assert k.alt_baslik == "En büyük 6 işlem · toplam 66 işlem, 4 üye"
    assert k.not_ == "+60 işlem daha aynı gün beyan edildi."
    ilk = k.satirlar[0]
    assert ilk.sag[0].kalin and ilk.sag[0].alt.startswith(secilen[0].yon)
    assert "56 gün geç" in ilk.sag[0].alt and ilk.sag[0].alt_vurgu
    assert "56 günde" in k.satirlar[1].sag[0].alt and not k.satirlar[1].sag[0].alt_vurgu
    _cizilir(k)
    assert gunluk_karti(secilen[:3], TARIH, 1, 3).not_ == ""


def test_uzun_ad_tasmaz():
    uzun = beyan(uye="Bartholomew Maximilian Alexander-Featherstonehaugh III", varlik="X" * 60, ticker="ABCDEFGH")
    _cizilir(gunluk_karti([uzun], TARIH, 1, 1))


def _ozet(t, alan, satan, partiler, iki=False):
    o = HisseOzeti(ticker=t, varlik=f"{t} Inc", alan_uyeler=set(alan), satan_uyeler=set(satan),
                   tutar_alt=16002, tutar_ust=100000)
    o.partiler.update(partiler)
    if iki:
        o.alan_partiler = {"D", "R"}
    return o


def test_haftalik_kart():
    ozet = [_ozet("TSM", ["a"], ["b"], {"D": 1, "R": 1}, iki=True), _ozet("HD", [], ["c", "d"], {"R": 2})] * 4
    k = haftalik_karti(ozet, datetime.date(2026, 10, 19))
    assert k.ad == "Haftanın Özeti" and k.tarih == "19–23.10.2026"
    assert len(k.satirlar) == 6
    assert k.satirlar[0].etiket == "iki parti" and k.satirlar[1].etiket == ""
    assert k.satirlar[0].sag[0].alt == "1 alan · 1 satan"
    assert "D 1, R 1" in k.satirlar[0].alt
    _cizilir(k)


def test_performans_kart():
    p = UyePerformansi("Josh Gottheimer", "D", "NJ", "Temsilciler", 10, 4.3, 0.2, 4.1, 0.8)
    q = UyePerformansi("Julie Johnson", "D", "TX", "Temsilciler", 17, -2.1, 12.5, -14.6, 0.18)
    yuksek = performans_karti([p] * 5, True, datetime.date(2026, 8, 5), datetime.date(2026, 11, 6))
    assert yuksek.ad == "Beyan Performansı: En Yüksek" and yuksek.tarih == "06.11.2026"
    assert yuksek.sutunlar == ("Üye", "Hisseler", "Fark")
    assert yuksek.not_ == kart.PERFORMANS_NOTU
    satir = yuksek.satirlar[0]
    assert satir.alt == "D-NJ · 10 alım"
    assert satir.sag[1].vurgu and satir.sag[1].kalin
    dusuk = performans_karti([q] * 2, False, datetime.date(2026, 8, 5), datetime.date(2026, 11, 6))
    assert dusuk.ad == "Beyan Performansı: En Düşük"
    _cizilir(yuksek)
    _cizilir(dusuk)


def test_basliklar():
    assert kart.performans_alt_basligi(datetime.date(2026, 8, 5), datetime.date(2026, 11, 6)) == \
        "Ağustos 2026'dan beri beyan edilen alımlar · en az 5 alım"
    assert kart.performans_alt_basligi(datetime.date(2025, 11, 6), datetime.date(2026, 11, 6)) == \
        "Son 12 ayda beyan edilen alımlar · en az 5 alım"
    assert kart.gunluk_alt_basligi(TARIH, 4, 66, 7) == "En büyük 7 işlem · toplam 66 işlem, 4 üye"
    assert kart.PERFORMANS_NOTU.startswith("Üyenin gerçek getirisi değildir")
