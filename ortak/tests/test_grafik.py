import io
from datetime import date, timedelta

import pytest
from PIL import Image

from rasathane_ortak import kagit
from rasathane_ortak.kagit import Grafik, Hucre, Isaret

MAVI = (45, 79, 214)
GOLGE = (235, 232, 223)
SOLUK_CIZGI = (179, 174, 162)


def _gunler(n=60):
    bas = date(2026, 7, 23)
    return tuple(bas + timedelta(days=i) for i in range(n))


def _grafik(**kw):
    gunler = kw.pop("gunler", _gunler())
    seri = kw.pop("seri", tuple(100 + (i % 7) * 2 - i * 0.1 for i in range(len(gunler))))
    return Grafik(fikir="INseeder", tarih="23.10.2026", baslik="RENT · Rent the Runway",
                  alt_baslik="Direktör · $3,88 Mn", gunler=gunler, seri=seri, kaynak="SEC EDGAR · Yahoo Finance",
                  ozet=(("Son kapanış", Hucre("$2,30", kalin=True)), ("Alım fiyatı", Hucre("$3,55", vurgu=True)),
                        ("Fark", Hucre("−%35,2"))), **kw)


def _resim(png):
    return Image.open(io.BytesIO(png)).convert("RGB")


def _renk_var(resim, renk):
    return any(c == renk for _, c in resim.getcolors(maxcolors=1 << 24))


def _ozetsiz(**kw):
    """Özetteki mavi sayı olmadan, yalnız grafik öğelerinin rengini ölçmek için."""
    g = _grafik(**kw)
    return Grafik(**{**g.__dict__, "ozet": tuple((a, Hucre(h.metin)) for a, h in g.ozet)})


def test_grafik_boyut():
    assert _resim(kagit.grafik_ciz(_grafik())).size == (1080, 1080)


def test_mavi_yalniz_isaret_ve_yatayla():
    assert not _renk_var(_resim(kagit.grafik_ciz(_ozetsiz())), MAVI)
    assert _renk_var(_resim(kagit.grafik_ciz(_ozetsiz(yatay=104.0, yatay_etiket="alım $3,55"))), MAVI)
    gunler = _gunler()
    assert _renk_var(_resim(kagit.grafik_ciz(_ozetsiz(isaretler=(Isaret(gunler[-1], "beyan 20.09"),)))), MAVI)


def test_golge_rengi():
    gunler = _gunler()
    assert not _renk_var(_resim(kagit.grafik_ciz(_grafik())), GOLGE)
    assert _renk_var(_resim(kagit.grafik_ciz(_grafik(golge=(gunler[30], gunler[50])))), GOLGE)


def test_karsilastirma_rengi():
    gunler = _gunler()
    assert not _renk_var(_resim(kagit.grafik_ciz(_grafik())), SOLUK_CIZGI)
    g = _grafik(karsilastirma=tuple(100 + i * 0.05 for i in range(len(gunler))), karsilastirma_adi="S&P 500")
    assert _renk_var(_resim(kagit.grafik_ciz(g)), SOLUK_CIZGI)


def test_isaret_seride_yoksa_hata():
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(isaretler=(Isaret(date(2020, 1, 1), "x"),)))
    gunler = _gunler()
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(golge=(gunler[3], date(2020, 1, 1))))


def test_uzunluk_uyusmazligi():
    gunler = _gunler()
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(seri=(1.0, 2.0)))
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(karsilastirma=(1.0,)))
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(gunler=gunler[:1], seri=(1.0,)))


def _kesisir(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def test_etiketler_cakismaz():
    f = kagit.font(24, True)
    dolu = [(int(x) - 4, int(y) - 4, int(x) + 4, int(y) + 4)
            for x, y in [(500 + i * 4, 600 - i) for i in range(60)]]
    adaylar = [(560, 585, "işlem 01.10"), (620, 570, "beyan 22.10"), (600, 575, "alım $3,55")]
    kutular = kagit._etiket_yerlestir(adaylar, dolu, f, (72, 450, 918, 880))
    assert len(kutular) == 3
    for i, k in enumerate(kutular):
        assert not any(_kesisir(k, d) for d in dolu), k
        assert not any(_kesisir(k, o) for j, o in enumerate(kutular) if j != i), k


def test_ozet_sag_kenara_tasmaz():
    g = _grafik()
    g = Grafik(**{**g.__dict__, "ozet": g.ozet[:2] + (("Fark", Hucre("−26,8 puan")),)})
    resim = _resim(kagit.grafik_ciz(g))
    bant = resim.crop((1080 - kagit.KENAR + 2, 300, 1080, 420))
    assert {c for _, c in bant.getcolors(maxcolors=1 << 16)} == {(246, 245, 240)}
