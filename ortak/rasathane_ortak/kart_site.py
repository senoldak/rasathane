"""Kâğıt kartlarını site verisine çevirir: `site-veri/<bölüm>/<önek>-<kart>.json`.

Her kart bir tablo sayfasıdır (grafiksiz). `Satir` tablo satırı olur: ilk sütun `ust`, ikinci `alt`,
sonrakiler `s0`, `s1`… (hücre metni). `Bolum` ögesi ayrı bir sütun taşımayan, yalnız ilk sütunda
başlık yazan satır olur. Kartın yalnız metin ögeleri alınır; çizim ve grafik bu modülün dışındadır.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from rasathane_ortak.kagit import Bolum, Kart, Satir
from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz

_CEVIR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
_AYIRICI = re.compile(r"[^a-z0-9]+")
_ALT_BASLIK = "Ayrıntı"


def slug(metin: str) -> str:
    """Türkçe harfleri sadeleştirir: 'En Çok İşlem Görenler' -> 'en-cok-islem-gorenler'."""
    return _AYIRICI.sub("-", metin.translate(_CEVIR).lower()).strip("-")[:40].strip("-")


def _hucre(h: object) -> str:
    metin = getattr(h, "metin", "")
    alt = getattr(h, "alt", "")
    return f"{metin} {alt}".strip() if alt else metin


def _sutunlar(kart: Kart, en_cok_sag: int) -> list[Sutun]:
    basliklar = list(kart.sutunlar)
    sutunlar = [Sutun("ust", basliklar[0] if basliklar else "Ad", "metin"), Sutun("alt", _ALT_BASLIK, "metin")]
    for i in range(en_cok_sag):
        baslik = basliklar[i + 1] if i + 1 < len(basliklar) else f"Değer {i + 1}"
        sutunlar.append(Sutun(f"s{i}", baslik, "metin"))
    return sutunlar


def _satirlar(kart: Kart) -> tuple[list[dict[str, object]], int]:
    sayi = max((len(o.sag) for o in kart.satirlar if isinstance(o, Satir)), default=0)
    satirlar: list[dict[str, object]] = []
    for oge in kart.satirlar:
        if isinstance(oge, Bolum):
            satir: dict[str, object] = {"ust": oge.baslik, "alt": ""}
            sag: tuple[object, ...] = ()
        elif isinstance(oge, Satir):
            satir = {"ust": oge.ust, "alt": oge.alt}
            sag = oge.sag
        else:
            continue
        for i in range(sayi):
            satir[f"s{i}"] = _hucre(sag[i]) if i < len(sag) else ""
        satirlar.append(satir)
    return satirlar, sayi


def kartlari_yaz(
    kok: Path,
    bolum: str,
    onek: str,
    kartlar: Sequence[Kart],
    *,
    simdi: datetime,
    kaynaklar: Sequence[Kaynak],
) -> list[Path]:
    """Her kartı `kok/bolum/<onek>-<kart>.json` olarak yazar ve yazılan yolları döndürür.

    Önek akışı ayırır (ör. `aksam`, `sabah`); aynı akışın bir sonraki koşusu kendi sayfalarını yeniler.
    Bu koşuda üretilmeyen eski sayfalar silinmez; `guncellendi` eskidiğinde sitede "eski veri" olarak görünür.
    """
    yollar: list[Path] = []
    for kart in kartlar:
        satirlar, sayi = _satirlar(kart)
        if not satirlar:
            continue
        yollar.append(
            sayfa_yaz(
                kok,
                bolum,
                f"{onek}-{slug(kart.ad)}",
                baslik=kart.ad,
                aciklama=kart.alt_baslik,
                guncellendi=simdi,
                kaynaklar=kaynaklar,
                sutunlar=_sutunlar(kart, sayi),
                satirlar=satirlar,
                grafik="yok",
            )
        )
    return yollar
