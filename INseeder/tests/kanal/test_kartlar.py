from datetime import date
from io import BytesIO

from PIL import Image

from inseeder.kanal.kartlar import gunluk_kart, haftalik_kart, sirket_unvan
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Bolum
from inseeder.kanal.secim import HaftalikOzet, KumeSatiri, Satir
from inseeder.kanal.takvim import hafta_gunleri
from tests.kanal.yardimci import beyan

GUN = date(2026, 10, 23)


def _ac(png: bytes) -> Image.Image:
    return Image.open(BytesIO(png))


def test_gunluk_kart_alanlari():
    kart = gunluk_kart(GUN, [Satir(beyan(sembol="RENT"), True, 0.15), Satir(beyan(sembol="NXG"), False, 0.22)])
    assert (kart.fikir, kart.ad, kart.tarih, kart.kaynak) == ("INseeder", "İçeriden Alımlar", "23.10.2026", "SEC EDGAR")
    kume, normal = kart.satirlar
    assert kume.ust == "RENT"
    assert kume.sag[0].kalin and kume.sag[0].alt == "küme" and kume.sag[0].alt_vurgu
    assert normal.sag[0].alt == "+22%" and not normal.sag[0].alt_vurgu


def test_gunluk_yeni_pozisyon():
    kart = gunluk_kart(GUN, [Satir(beyan(), False, "yeni")])
    assert kart.satirlar[0].sag[0].alt == "yeni pozisyon"


def test_gunluk_kart_cizilir():
    satirlar = [Satir(beyan(tutar=1e5 * (i + 1)), i % 2 == 0, "yeni") for i in range(8)]
    sayfalar = kagit.ciz(gunluk_kart(GUN, satirlar))
    assert all(_ac(s.png).width == 1080 for s in sayfalar)
    assert len(sayfalar) == 2


def test_haftalik_kart_bolumleri():
    gunler = hafta_gunleri(GUN)
    kart = haftalik_kart(HaftalikOzet(
        gunler,
        [KumeSatiri("AAA", "Aaa Corp", 3, 4.1e6)],
        [beyan(kod="S", tutar=6e6, unvan="CEO")],
    ))
    assert kart.ad == "Haftanın Özeti"
    assert kart.tarih == "19–23.10.2026"
    assert isinstance(kart.satirlar[0], Bolum) and "kümeleri" in kart.satirlar[0].baslik
    assert kart.satirlar[1].sag[0].alt == "3 kişi" and kart.satirlar[1].sag[0].alt_vurgu
    assert isinstance(kart.satirlar[2], Bolum) and "satışları" in kart.satirlar[2].baslik
    assert kart.satirlar[3].sag[0].alt.startswith("@ ")


def test_haftalik_bos_bolum_metni():
    kart = haftalik_kart(HaftalikOzet(hafta_gunleri(GUN), [], [beyan(kod="S", tutar=6e6, unvan="CEO")]))
    assert "yok" in kart.satirlar[1].alt
    assert kagit.ciz(kart)


def test_long_company_keeps_title():
    metin = sirket_unvan("Valdex Biotherapeutics Çağ İşletmeleri Şirketi Long Name", "Direktör")
    assert metin.endswith("… · Direktör")
