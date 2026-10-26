import io
from datetime import date

import pytest
from PIL import Image

from rasathane_ortak import kagit
from rasathane_ortak.kagit import Bolum, Hucre, Kart, Satir

MAVI = (45, 79, 214)


def _satirlar(n, vurgu=False):
    return tuple(
        Satir(ust=f"SMB{i}", alt=f"Şirket {i} · Direktör", sag=(Hucre("$1,25 Mn", kalin=True, vurgu=vurgu, alt="+%4"),))
        for i in range(n)
    )


def _kart(satirlar, **kw):
    return Kart(fikir="INseeder", ad="İçeriden Alımlar", tarih="23.10.2026",
                alt_baslik="SEC'e bildirilen açık piyasa alımları", satirlar=satirlar, kaynak="SEC EDGAR", **kw)


def _resim(png):
    return Image.open(io.BytesIO(png)).convert("RGB")


def _renk_var(resim, renk):
    return any(c == renk for _, c in resim.getcolors(maxcolors=1 << 24))


def test_tek_sayfa_boyut():
    sayfalar = kagit.ciz(_kart(_satirlar(5)))
    assert len(sayfalar) == 1
    s = sayfalar[0]
    assert (s.no, s.toplam) == (1, 1)
    assert s.satirlar == (0, 1, 2, 3, 4)
    assert _resim(s.png).size == (1080, 1080)


def test_zemin_ve_renkler():
    vurgusuz = _resim(kagit.ciz(_kart(_satirlar(3)))[0].png)
    assert vurgusuz.getpixel((0, 0)) == (246, 245, 240)
    assert not _renk_var(vurgusuz, MAVI)
    vurgulu = _resim(kagit.ciz(_kart(_satirlar(3, vurgu=True)))[0].png)
    assert _renk_var(vurgulu, MAVI)
    etiketli = _kart((Satir(ust="VRTX", etiket="FDA", alt="İlaç · Hastalık"),))
    assert _renk_var(_resim(kagit.ciz(etiketli)[0].png), MAVI)


def test_sayfalama():
    sayfalar = kagit.ciz(_kart(_satirlar(13)), sayfa_basina=6)
    assert [s.satirlar for s in sayfalar] == [tuple(range(6)), tuple(range(6, 12)), (12,)]
    assert all(s.toplam == 3 for s in sayfalar)
    assert [s.no for s in sayfalar] == [1, 2, 3]


def test_bolum_sayfada_tekrarlanir():
    kart = _kart((Bolum("A"),) + _satirlar(7))
    duzen = kagit._sayfa_duzeni(kart, 6)
    assert len(duzen) == 2
    assert duzen[1][0] == Bolum("A")
    sayfalar = kagit.ciz(kart, sayfa_basina=6)
    assert [s.satirlar for s in sayfalar] == [(1, 2, 3, 4, 5, 6), (7,)]


def test_uzun_ad_sag_sutuna_binmez():
    font = kagit.font(36, kalin=True)
    sinir = 400
    kisa = kagit._kisalt("Ç" * 200, font, sinir)
    assert kisa.endswith("…")
    assert font.getlength(kisa) <= sinir
    assert kagit._kisalt("RENT", font, sinir) == "RENT"


def test_uzun_metin_iki_satira_sarilir():
    font = kagit.font(30)
    metin = "Ağustos 2026'dan beri en az 5 alım beyan eden üyeler, S&P 500'e göre karşılaştırma ve ek açıklama"
    satirlar = kagit._sar(metin, font, 936)
    assert len(satirlar) == 2
    assert " ".join(satirlar).replace("…", "") .split() == metin.split()[: len(" ".join(satirlar).split())]
    assert all(font.getlength(s) <= 936 for s in satirlar)
    uc_satirlik = kagit._sar(metin * 3, font, 936)
    assert len(uc_satirlik) == 2 and uc_satirlik[1].endswith("…")
    assert kagit._sar("kısa", font, 936) == ["kısa"]


def test_mesaj_metni():
    assert kagit.mesaj_metni("biOF", "Sabah Bülteni", "23.10.2026") == "biOF · Sabah Bülteni · 23.10.2026"
    assert kagit.mesaj_metni("biOF", "Sabah Bülteni", "23.10.2026", 1, 2) == "biOF · Sabah Bülteni (1/2) · 23.10.2026"


def test_tarih_bicimleri():
    assert kagit.tarih_metni(date(2026, 10, 23)) == "23.10.2026"
    assert kagit.aralik_metni(date(2026, 10, 19), date(2026, 10, 23)) == "19–23.10.2026"
    assert kagit.aralik_metni(date(2026, 9, 28), date(2026, 10, 2)) == "28.09–02.10.2026"
    assert kagit.aralik_metni(date(2025, 12, 29), date(2026, 1, 2)) == "29.12.2025–02.01.2026"


def test_turkce_glifler():
    for kalin in (False, True):
        f = kagit.font(36, kalin=kalin)
        for c in "İıŞşĞğÜüÖöÇç·–−≥×…":
            assert f.getmask(c).getbbox() is not None, c


def test_bos_kart_hata():
    with pytest.raises(ValueError):
        kagit.ciz(_kart(()))


def test_alt_bilgide_uyari_hic_kisalmaz():
    f = kagit.font(26)
    metin = kagit._alt_bilgi("ClinicalTrials.gov · Yahoo Finance · SEC EDGAR · Ek Kaynak", f, 640)
    assert metin.endswith(" · Yatırım tavsiyesi değildir")
    assert "…" in metin and f.getlength(metin) <= 640
    assert kagit._alt_bilgi("SEC EDGAR", f, 640) == "SEC EDGAR · Yatırım tavsiyesi değildir"
