"""graFİX eklentisi: eğik/çoklu çizgi, boş temas noktası, çoklu yatay, hacim ve RSI alt paneli.

Yeni alanlar boşken eski grafikler bayt bayt aynı çizilir: `tests/veri/eski_*.png` eklentiden
önceki kagit.py ile üretildi (`python tests/test_grafik_eklenti.py` yeniden üretir; yalnız
çizimde bilerek değişiklik yapıldığında çalıştırın).
"""

import io
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from PIL import Image


from rasathane_ortak import kagit  # noqa: E402
from rasathane_ortak.kagit import Grafik, Hucre, Isaret  # noqa: E402

VERI = Path(__file__).resolve().parent / "veri"
MAVI = (45, 79, 214)
KAGIT = (246, 245, 240)
MUREKKEP = (21, 21, 21)
IKINCIL = (111, 107, 98)
CIZGI = (226, 223, 214)


def _gunler(n=60):
    bas = date(2026, 7, 23)
    return tuple(bas + timedelta(days=i) for i in range(n))


def _grafik(**kw):
    gunler = kw.pop("gunler", _gunler())
    seri = kw.pop("seri", tuple(100 + (i % 7) * 2 - i * 0.1 for i in range(len(gunler))))
    return Grafik(fikir="INseeder", tarih="23.10.2026", baslik="RENT · Rent the Runway",
                  alt_baslik="Direktör · $3,88 Mn", gunler=gunler, seri=seri,
                  kaynak="SEC EDGAR · Yahoo Finance",
                  ozet=(("Son kapanış", Hucre("$2,30", kalin=True)), ("Alım fiyatı", Hucre("$3,55", vurgu=True)),
                        ("Fark", Hucre("−%35,2"))), **kw)


def _ozetsiz(**kw):
    """Özetteki mavi sayı olmadan: yalnız grafik öğelerinin rengi ölçülür."""
    g = _grafik(**kw)
    return Grafik(**{**g.__dict__, "ozet": tuple((a, Hucre(h.metin)) for a, h in g.ozet)})


def _eski_ornekler():
    """Eklentiden önceki alanlarla dört kartın grafiği (INseeder, CAPitAL, biOF, OPsi türü)."""
    g = _gunler()
    return {
        "sade": _grafik(),
        "isaret_yatay": _grafik(
            seri_adi="RENT",
            isaretler=(Isaret(g[12], "işlem 03.08"), Isaret(g[-1], "beyan 20.09")),
            yatay=104.0,
            yatay_etiket="alım $3,55",
        ),
        "karsilastirma_golge": _grafik(
            seri_adi="NVDA",
            karsilastirma=tuple(100 + i * 0.05 for i in range(len(g))),
            karsilastirma_adi="S&P 500",
            golge=(g[30], g[50]),
            isaretler=(Isaret(g[30], "alım 22.08"),),
        ),
        "yuzde": _grafik(
            seri=tuple(20 + (i % 9) * 1.5 - i * 0.05 for i in range(len(g))),
            seri_adi="Örtük oynaklık",
            yuzde_eksen=True,
            yatay=24.0,
            yatay_etiket="ortalama %24,0",
            golge=(g[40], g[-1]),
        ),
    }


def _resim(png):
    return Image.open(io.BytesIO(png)).convert("RGB")


def _renk_var(resim, renk):
    return any(c == renk for _, c in resim.getcolors(maxcolors=1 << 24))


def _olcek(degerler, n, y0=kagit._G_Y0, y1=kagit._G_Y1):
    """grafik_ciz'in ana alan ölçeği: %8 pay, gün → x."""
    lo, hi = min(degerler), max(degerler)
    pay = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - pay, hi + pay

    def px(i):
        return kagit._G_X0 + (kagit._G_X1 - kagit._G_X0) * i / (n - 1)

    def py(v):
        return y1 - (y1 - y0) * (v - lo) / (hi - lo)

    return px, py


@pytest.mark.parametrize("ad", sorted(_eski_ornekler()))
def test_eski_grafik_ayni_png(ad):
    beklenen = (VERI / f"eski_{ad}.png").read_bytes()
    assert kagit.grafik_ciz(_eski_ornekler()[ad]) == beklenen


def test_egik_cizgi_mavi():
    g = _gunler()
    seri = tuple(100 + (i % 5) for i in range(len(g)))
    cizgi = kagit.Cizgi(noktalar=((g[10], 120.0), (g[50], 112.0)))
    resim = _resim(kagit.grafik_ciz(_ozetsiz(seri=seri, cizgiler=(cizgi,))))
    px, py = _olcek(list(seri) + [120.0, 112.0], len(g))
    assert resim.getpixel((round(px(30)), round(py(116.0)))) == MAVI


def test_ikincil_kesikli_cizgi_mavi_degil():
    g = _gunler()
    seri = tuple(100 + (i % 5) for i in range(len(g)))
    cizgi = kagit.Cizgi(noktalar=((g[10], 120.0), (g[50], 112.0)), ikincil=True, kesikli=True)
    resim = _resim(kagit.grafik_ciz(_ozetsiz(seri=seri, cizgiler=(cizgi,))))
    assert not _renk_var(resim, MAVI)
    assert _renk_var(resim, IKINCIL)


def test_bos_isaret_ici_kagit():
    g = _gunler()
    seri = tuple(100 + (i % 5) for i in range(len(g)))
    isaret = Isaret(g[20], "temas", deger=115.0, bos=True)
    resim = _resim(kagit.grafik_ciz(_ozetsiz(seri=seri, isaretler=(isaret,))))
    px, py = _olcek(list(seri) + [115.0], len(g))
    cx, cy = round(px(20)), round(py(115.0))
    assert resim.getpixel((cx, cy)) == KAGIT
    assert resim.getpixel((cx + 7, cy)) == MAVI
    assert resim.getpixel((cx, cy - 7)) == MAVI


def test_dolu_isaret_deger_ile():
    g = _gunler()
    seri = tuple(100 + (i % 5) for i in range(len(g)))
    isaret = Isaret(g[20], "kırılım", deger=115.0)
    resim = _resim(kagit.grafik_ciz(_ozetsiz(seri=seri, isaretler=(isaret,))))
    px, py = _olcek(list(seri) + [115.0], len(g))
    assert resim.getpixel((round(px(20)), round(py(115.0)))) == MAVI


def test_cizgi_olcege_girer():
    g = _gunler()
    seri = tuple(100 + (i % 11) for i in range(len(g)))
    cizgi = kagit.Cizgi(noktalar=((g[5], 104.0), (g[45], 150.0)))
    resim = _resim(kagit.grafik_ciz(_ozetsiz(seri=seri, cizgiler=(cizgi,))))
    _, py = _olcek(list(seri) + [104.0, 150.0], len(g))
    px, _ = _olcek(seri, len(g))
    uc = (round(px(45)), round(py(150.0)))
    assert kagit._G_Y0 <= uc[1] <= kagit._G_Y1
    assert resim.getpixel(uc) == MAVI
    bant = resim.crop((0, 440, 1080, kagit._G_Y0 - 6))
    assert not _renk_var(bant, MAVI)


def test_cizgi_son_gunden_ileri_kirpilir():
    g = _gunler()
    seri = tuple(100 + (i % 5) for i in range(len(g)))
    cizgi = kagit.Cizgi(noktalar=((g[30], 110.0), (g[-1] + timedelta(days=60), 100.0)))
    resim = _resim(kagit.grafik_ciz(_ozetsiz(seri=seri, cizgiler=(cizgi,))))
    sag = resim.crop((kagit._G_X1 + 3, kagit._G_Y0 - 10, 1080, kagit._G_Y1 + 10))
    assert not _renk_var(sag, MAVI)
    # Çizgi sağ kenara kadar uzar: son günün sütununda mavi var.
    sutun = resim.crop((kagit._G_X1 - 2, kagit._G_Y0, kagit._G_X1, kagit._G_Y1))
    assert _renk_var(sutun, MAVI)


def test_cizgi_gun_araliginin_tamami_disinda_hata_vermez():
    g = _gunler()
    cizgi = kagit.Cizgi(noktalar=((g[-1] + timedelta(days=5), 1.0), (g[-1] + timedelta(days=9), 2.0)))
    assert _resim(kagit.grafik_ciz(_ozetsiz(cizgiler=(cizgi,)))).size == (1080, 1080)


def test_cizgi_tek_nokta_hata():
    g = _gunler()
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(cizgiler=(kagit.Cizgi(noktalar=((g[3], 1.0),)),)))


def test_yataylar_iki_seviye():
    g = _gunler()
    seri = tuple(100 + (i % 5) for i in range(len(g)))
    gr = _ozetsiz(seri=seri, yataylar=((110.0, "direnç $110"), (95.0, "destek $95")))
    resim = _resim(kagit.grafik_ciz(gr))
    _, py = _olcek(list(seri) + [110.0, 95.0], len(g))
    for v in (110.0, 95.0):
        y = round(py(v))
        satir = [resim.getpixel((x, y)) for x in range(kagit._G_X0, kagit._G_X1)]
        assert satir.count(MAVI) > 0.4 * len(satir), v


def _hacim(n):
    return tuple(1000.0 + (i % 6) * 150 for i in range(n - 1)) + (4000.0,)


def test_hacim_paneli_vurgu_cubugu():
    g = _gunler()
    panel = kagit.AltPanel(tur="hacim", degerler=_hacim(len(g)), vurgu_gun=g[-1])
    resim = _resim(kagit.grafik_ciz(_ozetsiz(alt_panel=panel)))
    alt = kagit._G_Y1
    panel_ust = alt - round((kagit._G_Y1 - kagit._G_Y0) * 0.20)
    # Vurgu çubuğu (son gün, en yüksek hacim) mavi, panelin üstüne kadar uzanır.
    assert resim.getpixel((kagit._G_X1 - 1, alt - 3)) == MAVI
    assert resim.getpixel((kagit._G_X1 - 1, panel_ust + 3)) == MAVI
    # Diğer çubuklar ikincil renkte.
    assert _renk_var(resim.crop((kagit._G_X0, panel_ust, kagit._G_X1 - 20, alt)), IKINCIL)
    # Ana fiyat çizgisi panele inmez.
    assert not _renk_var(resim.crop((kagit._G_X0, panel_ust, kagit._G_X1 + 1, alt + 1)), MUREKKEP)


def test_panelsiz_vurgu_cubugu_yok():
    resim = _resim(kagit.grafik_ciz(_ozetsiz()))
    assert not _renk_var(resim, MAVI)


def test_rsi_paneli_cokmez():
    g = _gunler()
    rsi = tuple(50 + 30 * ((i % 10) / 10 - 0.5) for i in range(len(g)))
    panel = kagit.AltPanel(
        tur="rsi",
        degerler=rsi,
        seviyeler=(30.0, 70.0),
        cizgiler=(kagit.Cizgi(noktalar=((g[10], 40.0), (g[50], 55.0))),),
        isaretler=(Isaret(g[10], "", deger=40.0, bos=True), Isaret(g[50], "dip")),
    )
    resim = _resim(kagit.grafik_ciz(_ozetsiz(alt_panel=panel)))
    assert resim.size == (1080, 1080)
    panel_ust = kagit._G_Y1 - round((kagit._G_Y1 - kagit._G_Y0) * 0.34)
    bolge = resim.crop((kagit._G_X0, panel_ust, kagit._G_X1 + 1, kagit._G_Y1 + 1))
    assert _renk_var(bolge, MAVI)
    assert _renk_var(bolge, CIZGI)
    assert _renk_var(bolge, MUREKKEP)


def test_alt_panel_hatalari():
    g = _gunler()
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(alt_panel=kagit.AltPanel(tur="hacim", degerler=(1.0, 2.0))))
    with pytest.raises(ValueError):
        kagit.grafik_ciz(_grafik(alt_panel=kagit.AltPanel(tur="macd", degerler=_hacim(len(g)))))
    with pytest.raises(ValueError):
        panel = kagit.AltPanel(tur="hacim", degerler=_hacim(len(g)), vurgu_gun=date(2020, 1, 1))
        kagit.grafik_ciz(_grafik(alt_panel=panel))


if __name__ == "__main__":
    VERI.mkdir(exist_ok=True)
    for ad, grafik in _eski_ornekler().items():
        (VERI / f"eski_{ad}.png").write_bytes(kagit.grafik_ciz(grafik))
        print("yazıldı", ad)
