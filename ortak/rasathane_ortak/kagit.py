"""Rasathane Kâğıt kartı: dört fikrin ortak çizimi (Pillow)."""

from __future__ import annotations

import bisect
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import cache
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIZINI = Path(__file__).resolve().parent / "fontlar"

KAGIT = "#f6f5f0"
MUREKKEP = "#151515"
IKINCIL = "#6f6b62"
CIZGI = "#e2dfd6"
ALT_CIZGI = "#cfcbc0"
MAVI = "#2d4fd6"

GENISLIK = 1080
YUKSEKLIK = 1080
KENAR = 72
UYARI = "Yatırım tavsiyesi değildir"
KANAL = "t.me/rasathane"

_BASLIK_Y = 132
_ALT_BASLIK_Y = 224
_TABLO_Y = 292
_SUTUN_BASLIK_H = 46
_SATIR_H = 100
_TEK_SATIR_H = 72
_BOLUM_H = 62
_NOT_H = 48
_ALT_BILGI_H = 96
_SUTUN_ARASI = 40


@dataclass(frozen=True)
class Hucre:
    metin: str
    kalin: bool = False
    vurgu: bool = False
    ikincil: bool = False
    alt: str = ""
    alt_vurgu: bool = False


@dataclass(frozen=True)
class Satir:
    ust: str
    alt: str = ""
    etiket: str = ""
    sag: tuple[Hucre, ...] = ()


@dataclass(frozen=True)
class Bolum:
    baslik: str


@dataclass(frozen=True)
class Kart:
    fikir: str
    ad: str
    tarih: str
    alt_baslik: str
    satirlar: tuple[Satir | Bolum, ...]
    kaynak: str
    sutunlar: tuple[str, ...] = ()
    not_: str = ""


@dataclass(frozen=True)
class Sayfa:
    png: bytes
    no: int
    toplam: int
    satirlar: tuple[int, ...]


@cache
def font(boyut: int, kalin: bool = False) -> ImageFont.FreeTypeFont:
    ad = "Inter-Bold.ttf" if kalin else "Inter-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIZINI / ad), boyut)


def _kisalt(metin: str, f: ImageFont.FreeTypeFont, genislik: float) -> str:
    if f.getlength(metin) <= genislik:
        return metin
    while metin and f.getlength(metin + "…") > genislik:
        metin = metin[:-1]
    return metin.rstrip() + "…"


def _sar(metin: str, f: ImageFont.FreeTypeFont, genislik: float, azami: int = 2) -> list[str]:
    """Metni sözcük sınırından en çok `azami` satıra sarar; sığmayan son satır '…' ile kısalır."""
    satirlar: list[str] = []
    kelimeler = metin.split()
    while kelimeler and len(satirlar) < azami:
        satir = kelimeler.pop(0)
        while kelimeler and f.getlength(f"{satir} {kelimeler[0]}") <= genislik:
            satir += " " + kelimeler.pop(0)
        satirlar.append(satir)
    if kelimeler:
        satirlar[-1] = _kisalt(satirlar[-1] + " " + " ".join(kelimeler), f, genislik)
    return [_kisalt(s, f, genislik) for s in satirlar] or [""]


def _alt_bilgi(kaynak: str, f: ImageFont.FreeTypeFont, genislik: float) -> str:
    """Alt bilginin sol metni: uyarı hiç kısalmaz, sığmazsa kaynak kısalır."""
    if not kaynak:
        return UYARI
    ek = f" · {UYARI}"
    return _kisalt(kaynak, f, genislik - f.getlength(ek)) + ek


def tarih_metni(g: date) -> str:
    return f"{g:%d.%m.%Y}"


def aralik_metni(bas: date, son: date) -> str:
    if bas.year != son.year:
        return f"{bas:%d.%m.%Y}–{son:%d.%m.%Y}"
    if bas.month != son.month:
        return f"{bas:%d.%m}–{son:%d.%m.%Y}"
    return f"{bas:%d}–{son:%d.%m.%Y}"


def mesaj_metni(fikir: str, ad: str, tarih: str, no: int = 1, toplam: int = 1) -> str:
    ek = f" ({no}/{toplam})" if toplam > 1 else ""
    return f"{fikir} · {ad}{ek} · {tarih}"


def _sayfa_duzeni(kart: Kart, sayfa_basina: int) -> list[list[Satir | Bolum]]:
    """Ögeleri sayfalara böler; bölüm ortasında kesilen sayfada bölüm başlığı tekrarlanır."""
    sayfalar: list[list[Satir | Bolum]] = [[]]
    sayi = 0
    son_bolum: Bolum | None = None
    for oge in kart.satirlar:
        if isinstance(oge, Bolum):
            son_bolum = oge
            if sayi >= sayfa_basina:
                sayfalar.append([])
                sayi = 0
            sayfalar[-1].append(oge)
            continue
        if sayi >= sayfa_basina:
            sayfalar.append([son_bolum] if son_bolum else [])
            sayi = 0
        sayfalar[-1].append(oge)
        sayi += 1
    return sayfalar


def _hucre_fontu(h: Hucre) -> ImageFont.FreeTypeFont:
    return font(28 if h.ikincil else 36, kalin=h.kalin)


def _hucre_rengi(vurgu: bool, ikincil: bool) -> str:
    if vurgu:
        return MAVI
    return IKINCIL if ikincil else MUREKKEP


def _sutun_genislikleri(kart: Kart, icerik: int) -> list[float]:
    sutun_sayisi = max((len(o.sag) for o in kart.satirlar if isinstance(o, Satir)), default=0)
    sutun_sayisi = max(sutun_sayisi, len(kart.sutunlar) - 1)
    azami = icerik * 0.45
    genislik = [0.0] * sutun_sayisi
    for j in range(sutun_sayisi):
        if j + 1 < len(kart.sutunlar):
            genislik[j] = font(24).getlength(kart.sutunlar[j + 1])
    for o in kart.satirlar:
        if not isinstance(o, Satir):
            continue
        for j, h in enumerate(o.sag):
            g = max(_hucre_fontu(h).getlength(h.metin), font(28).getlength(h.alt) if h.alt else 0)
            genislik[j] = max(genislik[j], min(g, azami))
    return genislik


def _iki_satirli(kart: Kart) -> bool:
    return any(isinstance(o, Satir) and (o.alt or any(h.alt for h in o.sag)) for o in kart.satirlar)


def _sayfa_ciz(kart: Kart, ogeler: list[Satir | Bolum], no: int, toplam: int) -> bytes:
    icerik = GENISLIK - 2 * KENAR
    alt_baslik = _sar(kart.alt_baslik, font(30), icerik)
    notlar = _sar(kart.not_, font(24), icerik) if kart.not_ else []
    tablo_y = _TABLO_Y + 40 * (len(alt_baslik) - 1)
    satir_h = _SATIR_H if _iki_satirli(kart) else _TEK_SATIR_H
    govde = sum(_BOLUM_H if isinstance(o, Bolum) else satir_h for o in ogeler)
    gerekli = (
        tablo_y
        + (_SUTUN_BASLIK_H if kart.sutunlar else 0)
        + govde
        + (_NOT_H + 32 * (len(notlar) - 1) if notlar else 0)
        + 24
        + _ALT_BILGI_H
    )
    yukseklik = max(YUKSEKLIK, gerekli)

    resim = Image.new("RGB", (GENISLIK, yukseklik), KAGIT)
    d = ImageDraw.Draw(resim)
    sag_kenar = GENISLIK - KENAR

    d.text((KENAR, 64), kart.fikir, font=font(30, True), fill=MUREKKEP)
    d.text((sag_kenar, 64), kart.tarih, font=font(30), fill=IKINCIL, anchor="ra")

    baslik = kart.ad + (f" ({no}/{toplam})" if toplam > 1 else "")
    boyut = 64
    while boyut > 40 and font(boyut, True).getlength(baslik) > icerik:
        boyut -= 2
    d.text(
        (KENAR, _BASLIK_Y),
        _kisalt(baslik, font(boyut, True), icerik),
        font=font(boyut, True),
        fill=MUREKKEP,
    )
    for i, satir in enumerate(alt_baslik):
        d.text((KENAR, _ALT_BASLIK_Y + 40 * i), satir, font=font(30), fill=IKINCIL)

    genislik = _sutun_genislikleri(kart, icerik)
    sag_x: list[float] = []
    x: float = sag_kenar
    for g in reversed(genislik):
        sag_x.insert(0, x)
        x -= g + _SUTUN_ARASI
    sol_sinir = (sag_x[0] - genislik[0] - 24 if genislik else sag_kenar) - KENAR

    y = tablo_y
    if kart.sutunlar:
        d.text((KENAR, y), kart.sutunlar[0], font=font(24), fill=IKINCIL)
        for j, ad in enumerate(kart.sutunlar[1:]):
            d.text((sag_x[j], y), ad, font=font(24), fill=IKINCIL, anchor="ra")
        y += _SUTUN_BASLIK_H

    for oge in ogeler:
        if isinstance(oge, Bolum):
            d.text(
                (KENAR, y + 22),
                _kisalt(oge.baslik, font(26, True), icerik),
                font=font(26, True),
                fill=MUREKKEP,
            )
            y += _BOLUM_H
            continue
        d.line((KENAR, y, sag_kenar, y), fill=CIZGI, width=2)
        ust_f = font(36, True)
        etiket_f = font(22, True)
        etiket_g = etiket_f.getlength(oge.etiket) + 16 if oge.etiket else 0
        ust = _kisalt(oge.ust, ust_f, sol_sinir - etiket_g)
        d.text((KENAR, y + 16), ust, font=ust_f, fill=MUREKKEP)
        if oge.etiket:
            ex = KENAR + ust_f.getlength(ust) + 16
            d.text(
                (ex, y + 16 + ust_f.getbbox("A")[3]),
                oge.etiket.upper(),
                font=etiket_f,
                fill=MAVI,
                anchor="ls",
            )
        if oge.alt:
            d.text(
                (KENAR, y + 60), _kisalt(oge.alt, font(28), sol_sinir), font=font(28), fill=IKINCIL
            )
        for j, h in enumerate(oge.sag):
            hf = _hucre_fontu(h)
            metin = _kisalt(h.metin, hf, genislik[j])
            ust_y = y + 16 if hf.size == 36 else y + 20
            d.text(
                (sag_x[j], ust_y),
                metin,
                font=hf,
                fill=_hucre_rengi(h.vurgu, h.ikincil),
                anchor="ra",
            )
            if h.alt:
                d.text(
                    (sag_x[j], y + 60),
                    _kisalt(h.alt, font(28), genislik[j]),
                    font=font(28),
                    fill=_hucre_rengi(h.alt_vurgu, True),
                    anchor="ra",
                )
        y += satir_h

    for i, satir in enumerate(notlar):
        d.text((KENAR, y + 16 + 32 * i), satir, font=font(24), fill=IKINCIL)

    alt_y = yukseklik - _ALT_BILGI_H
    d.line((KENAR, alt_y, sag_kenar, alt_y), fill=ALT_CIZGI, width=2)
    kanal_f = font(26, True)
    kanal_g = kanal_f.getlength(KANAL)
    orta = alt_y + _ALT_BILGI_H // 2
    d.text(
        (KENAR, orta),
        _alt_bilgi(kart.kaynak, font(26), icerik - kanal_g - 32),
        font=font(26),
        fill=IKINCIL,
        anchor="lm",
    )
    d.text((sag_kenar, orta), KANAL, font=kanal_f, fill=MUREKKEP, anchor="rm")

    tampon = io.BytesIO()
    resim.save(tampon, "PNG", optimize=True)
    return tampon.getvalue()


GOLGE = "#ebe8df"
SOLUK_CIZGI = "#b3aea2"
_G_X0, _G_X1, _G_Y0, _G_Y1 = KENAR, GENISLIK - KENAR - 90, 470, 870
Kutu = tuple[int, int, int, int]  # (sol, üst, sağ, alt)
Nokta = tuple[float, float]
_PANEL_ORANI = {"hacim": 0.20, "rsi": 0.34}
_PANEL_ARASI = 24


@dataclass(frozen=True)
class Isaret:
    """Grafikte bir gün. `deger` yoksa nokta serinin o günkü değerine konur; `bos` iken içi kâğıt."""

    gun: date
    etiket: str
    deger: float | None = None
    bos: bool = False


@dataclass(frozen=True)
class Cizgi:
    """Seri biriminde kırık çizgi; grafik günleri dışında kalan kısmı alanın kenarında kesilir."""

    noktalar: tuple[tuple[date, float], ...]
    ikincil: bool = False
    kesikli: bool = False
    etiket: str = ""


@dataclass(frozen=True)
class AltPanel:
    """Grafiğin altında "hacim" (çubuk, alanın alt %20'si) ya da "rsi" (çizgi, alt %34, 0–100)."""

    tur: str
    degerler: tuple[float, ...]
    vurgu_gun: date | None = None
    cizgiler: tuple[Cizgi, ...] = ()
    isaretler: tuple[Isaret, ...] = ()
    seviyeler: tuple[float, ...] = ()


@dataclass(frozen=True)
class Grafik:
    """Çizgi grafik kartı. `yuzde_eksen` iken seri değerleri yüzde birimindedir (23,4 = %23,4)."""

    fikir: str
    tarih: str
    baslik: str
    alt_baslik: str
    ozet: tuple[tuple[str, Hucre], ...]
    gunler: tuple[date, ...]
    seri: tuple[float, ...]
    kaynak: str
    seri_adi: str = ""
    karsilastirma: tuple[float, ...] | None = None
    karsilastirma_adi: str = ""
    isaretler: tuple[Isaret, ...] = ()
    golge: tuple[date, date] | None = None
    yatay: float | None = None
    yatay_etiket: str = ""
    yuzde_eksen: bool = False
    cizgiler: tuple[Cizgi, ...] = ()
    yataylar: tuple[tuple[float, str], ...] = ()
    alt_panel: AltPanel | None = None


def _tr(x: float, basamak: int = 2) -> str:
    return f"{x:,.{basamak}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _kesisir(a: Kutu, b: Kutu) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


_ETIKET_YERLERI = [
    (-16, -18, "rd"),
    (16, -18, "ld"),
    (16, 18, "la"),
    (-16, 18, "ra"),
    (-16, -50, "rd"),
    (16, -50, "ld"),
    (16, 50, "la"),
    (-16, 50, "ra"),
]


def _etiket_yerlestir(
    adaylar: list[tuple[float, float, str]], dolu: list[Kutu], f: ImageFont.FreeTypeFont, alan: Kutu
) -> list[Kutu]:
    """Her etiketi noktasının çevresinde çizgilere ve önceki etiketlere değmeyen ilk yere koyar."""
    yerlesen: list[Kutu] = []
    for x, y, metin in adaylar:
        secilen = None
        for dx, dy, capa in _ETIKET_YERLERI:
            sol, ust, sag, alt = f.getbbox(metin, anchor=capa)
            k = (
                int(x + dx + sol) - 4,
                int(y + dy + ust) - 4,
                int(x + dx + sag) + 4,
                int(y + dy + alt) + 4,
            )
            if k[0] < alan[0] or k[1] < alan[1] or k[2] > alan[2] or k[3] > alan[3]:
                continue
            if secilen is None:
                secilen = k
            if not any(_kesisir(k, d) for d in dolu) and not any(_kesisir(k, o) for o in yerlesen):
                secilen = k
                break
        yerlesen.append(secilen or (int(x), int(y), int(x), int(y)))
    return yerlesen


def _gun_sirasi(gunler: tuple[date, ...], gun: date) -> float:
    """Günün seri içindeki (kesirli) sırası; aradaki ve dışarıdaki günler takvimle oranlanır."""
    ilk, son = gunler[0], gunler[-1]
    if gun <= ilk or gun >= son:
        oran = (len(gunler) - 1) / max((son - ilk).days, 1)
        if gun >= son:
            return len(gunler) - 1 + (gun - son).days * oran
        return (gun - ilk).days * oran
    j = bisect.bisect_left(gunler, gun)
    if gunler[j] == gun:
        return float(j)
    a, b = gunler[j - 1], gunler[j]
    return j - 1 + (gun - a).days / (b - a).days


def _kirp(p: Nokta, q: Nokta, son: float) -> tuple[Nokta, Nokta] | None:
    """(sıra, değer) parçasını 0..son sıra aralığına keser; tamamen dışarıdaysa None."""
    (i0, v0), (i1, v1) = p, q
    if i0 == i1:
        return (p, q) if 0 <= i0 <= son else None
    t_a, t_b = (0 - i0) / (i1 - i0), (son - i0) / (i1 - i0)
    t0, t1 = max(0.0, min(t_a, t_b)), min(1.0, max(t_a, t_b))
    if t0 > t1:
        return None
    return (
        (i0 + (i1 - i0) * t0, v0 + (v1 - v0) * t0),
        (i0 + (i1 - i0) * t1, v0 + (v1 - v0) * t1),
    )


def _cizgi_parcalari(c: Cizgi, gunler: tuple[date, ...]) -> list[list[Nokta]]:
    """Çizginin grafik günleri içinde kalan kırık çizgileri, (sıra, değer) biriminde."""
    if len(c.noktalar) < 2:
        raise ValueError("Çizgide en az iki nokta olmalı")
    ham = [(_gun_sirasi(gunler, gun), v) for gun, v in c.noktalar]
    parcalar: list[list[Nokta]] = []
    for p, q in pairwise(ham):
        kesik = _kirp(p, q, len(gunler) - 1)
        if kesik is None:
            continue
        if parcalar and parcalar[-1][-1] == kesik[0]:
            parcalar[-1].append(kesik[1])
        else:
            parcalar.append([kesik[0], kesik[1]])
    return parcalar


def _yol_kutulari(noktalar: list[Nokta], yari: int) -> list[Kutu]:
    """Etiket yerleşimi için kırık çizgi boyunca ~6 pikselde bir küçük kutu."""
    kutular: list[Kutu] = []
    for (x0, y0), (x1, y1) in pairwise(noktalar):
        adim = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / 6))
        for k in range(adim + 1):
            x, y = x0 + (x1 - x0) * k / adim, y0 + (y1 - y0) * k / adim
            kutular.append((int(x) - yari, int(y) - yari, int(x) + yari, int(y) + yari))
    return kutular


def _kesikli_ciz(d: ImageDraw.ImageDraw, noktalar: list[Nokta], renk: str, kalinlik: int) -> None:
    """Kırık çizgiyi 14 piksel dolu, 10 piksel boş kesiklerle çizer."""
    faz = 0.0
    for (x0, y0), (x1, y1) in pairwise(noktalar):
        uzunluk = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        s = -faz
        while s < uzunluk:
            a, b = max(s, 0.0), min(s + 14, uzunluk)
            if b > a:
                d.line(
                    [
                        (x0 + (x1 - x0) * a / uzunluk, y0 + (y1 - y0) * a / uzunluk),
                        (x0 + (x1 - x0) * b / uzunluk, y0 + (y1 - y0) * b / uzunluk),
                    ],
                    fill=renk,
                    width=kalinlik,
                )
            s += 24
        faz = (faz + uzunluk) % 24


def _isaret_ciz(d: ImageDraw.ImageDraw, cx: float, cy: float, bos: bool) -> None:
    if bos:
        d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=KAGIT, outline=MAVI, width=3)
    else:
        d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=MAVI, outline=KAGIT, width=3)


def _dogrula(g: Grafik, gun_indeksi: dict[date, int]) -> None:
    n = len(g.gunler)
    if n < 2 or len(g.seri) != n:
        raise ValueError("Grafikte en az iki gün olmalı ve seri günlerle aynı uzunlukta olmalı")
    if g.karsilastirma is not None and len(g.karsilastirma) != n:
        raise ValueError("Karşılaştırma serisi günlerle aynı uzunlukta olmalı")
    gunler = [i.gun for i in g.isaretler] + list(g.golge or ())
    p = g.alt_panel
    if p is not None:
        if p.tur not in _PANEL_ORANI:
            raise ValueError(f"Bilinmeyen alt panel türü: {p.tur}")
        if len(p.degerler) != n:
            raise ValueError("Alt panel değerleri günlerle aynı uzunlukta olmalı")
        gunler += [i.gun for i in p.isaretler] + ([p.vurgu_gun] if p.vurgu_gun else [])
    for gun in gunler:
        if gun not in gun_indeksi:
            raise ValueError(f"{gun} grafik günleri içinde değil")
    for c in g.cizgiler + (p.cizgiler if p else ()):
        if len(c.noktalar) < 2:
            raise ValueError("Çizgide en az iki nokta olmalı")


def _cizgileri_ciz(
    d: ImageDraw.ImageDraw,
    cizgiler: list[tuple[Cizgi, list[list[Nokta]]]],
    dolu: list[Kutu],
) -> list[tuple[float, float, str, str]]:
    """Piksel birimindeki çizgileri çizer, `dolu`ya ekler; uç etiketi adaylarını döndürür."""
    adaylar: list[tuple[float, float, str, str]] = []
    for c, parcalar in cizgiler:
        renk, kalinlik = (IKINCIL, 2) if c.ikincil else (MAVI, 4)
        for noktalar in parcalar:
            if c.kesikli:
                _kesikli_ciz(d, noktalar, renk, kalinlik)
            else:
                d.line(noktalar, fill=renk, width=kalinlik, joint="curve")
            dolu += _yol_kutulari(noktalar, kalinlik // 2 + 3)
        if c.etiket and parcalar:
            x, y = parcalar[-1][-1]
            adaylar.append((x, y, c.etiket, renk))
    return adaylar


def _alt_panel_ciz(
    d: ImageDraw.ImageDraw,
    p: AltPanel,
    gunler: tuple[date, ...],
    px: Callable[[float], float],
    ust: int,
) -> None:
    n = len(gunler)
    gun_indeksi = {gun: i for i, gun in enumerate(gunler)}
    alt = _G_Y1
    if p.tur == "rsi":
        lo, hi = 0.0, 100.0
    else:
        lo, hi = 0.0, max(max(p.degerler), 0.0) or 1.0

    def py(v: float) -> float:
        return alt - (alt - ust) * (min(max(v, lo), hi) - lo) / (hi - lo)

    for v in p.seviyeler:
        d.line([(_G_X0, py(v)), (_G_X1, py(v))], fill=CIZGI, width=2)
        d.text((_G_X1 + 14, py(v)), _tr(v, 0), font=font(20), fill=IKINCIL, anchor="lm")

    dolu: list[Kutu] = []
    if p.tur == "hacim":
        yari = max(0.5, (_G_X1 - _G_X0) / (n - 1) * 0.3)
        vurgu = gun_indeksi[p.vurgu_gun] if p.vurgu_gun else -1
        for i, v in enumerate(p.degerler):
            if v <= 0:
                continue
            x = px(i)
            renk = MAVI if i == vurgu else IKINCIL
            d.rectangle([max(x - yari, _G_X0), py(v), min(x + yari, _G_X1), alt], fill=renk)
            dolu.append((int(x - yari), int(py(v)), int(x + yari), alt))
    else:
        noktalar = [(px(i), py(v)) for i, v in enumerate(p.degerler)]
        d.line(noktalar, fill=MUREKKEP, width=3, joint="curve")
        dolu += [(int(x) - 4, int(y) - 4, int(x) + 4, int(y) + 4) for x, y in noktalar]

    cizgiler = [
        (c, [[(px(i), py(v)) for i, v in pr] for pr in _cizgi_parcalari(c, gunler)])
        for c in p.cizgiler
    ]
    uc_adaylari = _cizgileri_ciz(d, cizgiler, dolu)
    yerler = [
        (gun_indeksi[i.gun], i.deger if i.deger is not None else p.degerler[gun_indeksi[i.gun]])
        for i in p.isaretler
    ]
    adaylar = [(px(j), py(v), i.etiket) for (j, v), i in zip(yerler, p.isaretler) if i.etiket]
    renkler = [MAVI] * len(adaylar) + [renk for *_, renk in uc_adaylari]
    adaylar += [(x, y, metin) for x, y, metin, _ in uc_adaylari]
    f = font(22, True)
    kutular = _etiket_yerlestir(adaylar, dolu, f, (_G_X0, ust - 10, _G_X1, alt + 10))
    for (_, _, metin), k, renk in zip(adaylar, kutular, renkler):
        d.text((k[0] + 4, k[1] + 4), metin, font=f, fill=renk, anchor="lt")
    for (j, v), isaret in zip(yerler, p.isaretler):
        _isaret_ciz(d, px(j), py(v), isaret.bos)


def grafik_ciz(g: Grafik) -> bytes:
    n = len(g.gunler)
    gun_indeksi = {gun: i for i, gun in enumerate(g.gunler)}
    _dogrula(g, gun_indeksi)

    resim = Image.new("RGB", (GENISLIK, YUKSEKLIK), KAGIT)
    d = ImageDraw.Draw(resim)
    icerik = GENISLIK - 2 * KENAR
    sag_kenar = GENISLIK - KENAR

    d.text((KENAR, 64), g.fikir, font=font(30, True), fill=MUREKKEP)
    d.text((sag_kenar, 64), g.tarih, font=font(30), fill=IKINCIL, anchor="ra")
    boyut = 60
    while boyut > 40 and font(boyut, True).getlength(g.baslik) > icerik:
        boyut -= 2
    d.text(
        (KENAR, 132),
        _kisalt(g.baslik, font(boyut, True), icerik),
        font=font(boyut, True),
        fill=MUREKKEP,
    )
    d.text((KENAR, 218), _kisalt(g.alt_baslik, font(30), icerik), font=font(30), fill=IKINCIL)

    for i, (etiket, h) in enumerate(g.ozet[:3]):
        x = KENAR + 340 * i
        d.text((x, 296), etiket, font=font(26), fill=IKINCIL)
        genislik = min(320, sag_kenar - x)
        boyut = 52
        while boyut > 36 and font(boyut, True).getlength(h.metin) > genislik:
            boyut -= 2
        d.text(
            (x, 332 + (52 - boyut) // 2),
            _kisalt(h.metin, font(boyut, True), genislik),
            font=font(boyut, True),
            fill=MAVI if h.vurgu else MUREKKEP,
        )

    # Ana alan: alt panel varsa onun yüksekliği ve bir boşluk kadar kısalır.
    y1 = _G_Y1
    panel_ust = _G_Y1
    if g.alt_panel is not None:
        panel_ust = _G_Y1 - round((_G_Y1 - _G_Y0) * _PANEL_ORANI[g.alt_panel.tur])
        y1 = panel_ust - _PANEL_ARASI

    seviyeler = ([(g.yatay, g.yatay_etiket)] if g.yatay is not None else []) + list(g.yataylar)
    cizgi_parcalari = [(c, _cizgi_parcalari(c, g.gunler)) for c in g.cizgiler]
    hepsi = list(g.seri) + list(g.karsilastirma or ()) + [v for v, _ in seviyeler]
    hepsi += [v for _, pr in cizgi_parcalari for parca in pr for _, v in parca]
    hepsi += [i.deger for i in g.isaretler if i.deger is not None]
    lo, hi = min(hepsi), max(hepsi)
    pay = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - pay, hi + pay

    def px(i: float) -> float:
        return _G_X0 + (_G_X1 - _G_X0) * i / (n - 1)

    def py(v: float) -> float:
        return y1 - (y1 - _G_Y0) * (v - lo) / (hi - lo)

    def deger(v: float) -> str:
        return f"%{_tr(v, 1)}" if g.yuzde_eksen else _tr(v)

    if g.golge:
        a, b = sorted(gun_indeksi[x] for x in g.golge)
        d.rectangle([px(a), _G_Y0 - 20, px(b), _G_Y1 + 10], fill=GOLGE)

    for v in (min(g.seri), max(g.seri)):
        d.line([(_G_X0, py(v)), (_G_X1, py(v))], fill=CIZGI, width=2)
        d.text((_G_X1 + 14, py(v)), deger(v), font=font(24), fill=IKINCIL, anchor="lm")

    dolu: list[Kutu] = []
    for v, _ in seviyeler:
        ya = py(v)
        cx = float(_G_X0)
        while cx < _G_X1:
            d.line([(cx, ya), (min(cx + 14, _G_X1), ya)], fill=MAVI, width=3)
            cx += 24
        dolu.append((_G_X0, int(ya) - 3, _G_X1, int(ya) + 3))

    if g.alt_panel is not None:
        _alt_panel_ciz(d, g.alt_panel, g.gunler, px, panel_ust)

    if g.karsilastirma is not None:
        noktalar = [(px(i), py(v)) for i, v in enumerate(g.karsilastirma)]
        d.line(noktalar, fill=SOLUK_CIZGI, width=3, joint="curve")
        dolu += [(int(x) - 4, int(y) - 4, int(x) + 4, int(y) + 4) for x, y in noktalar]
        if g.karsilastirma_adi:
            d.text(
                (noktalar[-1][0] + 14, noktalar[-1][1]),
                g.karsilastirma_adi,
                font=font(22),
                fill=SOLUK_CIZGI,
                anchor="lm",
            )

    noktalar = [(px(i), py(v)) for i, v in enumerate(g.seri)]
    d.line(noktalar, fill=MUREKKEP, width=4, joint="curve")
    dolu += [(int(x) - 5, int(y) - 5, int(x) + 5, int(y) + 5) for x, y in noktalar]
    if g.seri_adi:
        d.text((_G_X0, _G_Y0 - 32), g.seri_adi, font=font(24, True), fill=MUREKKEP, anchor="ld")

    uc_adaylari = _cizgileri_ciz(
        d,
        [(c, [[(px(i), py(v)) for i, v in pr] for pr in prs]) for c, prs in cizgi_parcalari],
        dolu,
    )

    def isaret_yeri(i: Isaret) -> Nokta:
        x, y = noktalar[gun_indeksi[i.gun]]
        return (x, y) if i.deger is None else (x, py(i.deger))

    etiket_f = font(24, True)
    alan = (_G_X0, _G_Y0 - 30, _G_X1, y1 + 10)
    adaylar = [(*isaret_yeri(i), i.etiket) for i in g.isaretler]
    adaylar += [(_G_X0 + 4, py(v), metin) for v, metin in seviyeler if metin]
    kutular = _etiket_yerlestir(adaylar, dolu, etiket_f, alan)
    for (_, _, metin), k in zip(adaylar, kutular):
        d.text((k[0] + 4, k[1] + 4), metin, font=etiket_f, fill=MAVI, anchor="lt")
    if uc_adaylari:
        uc_f = font(22, True)
        uc_kutulari = _etiket_yerlestir(
            [(x, y, metin) for x, y, metin, _ in uc_adaylari], dolu + kutular, uc_f, alan
        )
        for (_, _, metin, renk), k in zip(uc_adaylari, uc_kutulari):
            d.text((k[0] + 4, k[1] + 4), metin, font=uc_f, fill=renk, anchor="lt")
    for isaret in g.isaretler:
        _isaret_ciz(d, *isaret_yeri(isaret), isaret.bos)

    d.text((_G_X0, _G_Y1 + 22), f"{g.gunler[0]:%d.%m}", font=font(24), fill=IKINCIL)
    d.text((_G_X1, _G_Y1 + 22), f"{g.gunler[-1]:%d.%m}", font=font(24), fill=IKINCIL, anchor="ra")

    alt_y = YUKSEKLIK - _ALT_BILGI_H
    d.line((KENAR, alt_y, sag_kenar, alt_y), fill=ALT_CIZGI, width=2)
    kanal_f = font(26, True)
    orta = alt_y + _ALT_BILGI_H // 2
    d.text(
        (KENAR, orta),
        _alt_bilgi(g.kaynak, font(26), icerik - kanal_f.getlength(KANAL) - 32),
        font=font(26),
        fill=IKINCIL,
        anchor="lm",
    )
    d.text((sag_kenar, orta), KANAL, font=kanal_f, fill=MUREKKEP, anchor="rm")

    tampon = io.BytesIO()
    resim.save(tampon, "PNG", optimize=True)
    return tampon.getvalue()


def ciz(kart: Kart, sayfa_basina: int = 6) -> list[Sayfa]:
    if not any(isinstance(o, Satir) for o in kart.satirlar):
        raise ValueError("Kartta en az bir satır olmalı")
    duzen = _sayfa_duzeni(kart, sayfa_basina)
    kimlik = {id(o): i for i, o in enumerate(kart.satirlar)}
    toplam = len(duzen)
    sonuc = []
    for no, ogeler in enumerate(duzen, 1):
        indeksler = tuple(kimlik[id(o)] for o in ogeler if isinstance(o, Satir))
        sonuc.append(Sayfa(_sayfa_ciz(kart, ogeler, no, toplam), no, toplam, indeksler))
    return sonuc
