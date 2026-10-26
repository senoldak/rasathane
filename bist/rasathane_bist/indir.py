"""Borsa İstanbul dosyalarını indirme: enjekte edilebilir indirici, yeniden deneme."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date

# url -> (durum kodu, gövde); yönlendirmeyi izler
Indirici = Callable[[str], tuple[int, bytes]]

BEKLEME_SN = 5


class BistErisimHatasi(Exception):
    """Dosya, denemeler bittikten sonra da alınamadı."""


def pay_bulteni_url(gun: date) -> str:
    """Günün pay bülteni (THB) zip adresi."""
    return f"https://borsaistanbul.com/data/thb/{gun:%Y}/{gun:%m}/thb{gun:%Y%m%d}1.zip"


def dosya_al(
    indirici: Indirici,
    url: str,
    deneme: int = 3,
    uyku: Callable[[float], None] = time.sleep,
) -> bytes | None:
    """200 ise gövdeyi, 404 ise None döndürür; diğer durum/istisna için yeniden dener."""
    son = "deneme yapılmadı"
    for sira in range(deneme):
        if sira:
            uyku(BEKLEME_SN)
        try:
            durum, govde = indirici(url)
        except Exception as hata:  # noqa: BLE001 - her ağ hatası başarısız deneme sayılır
            son = f"istisna: {hata!r}"
            continue
        if durum == 200:
            return govde
        if durum == 404:
            return None
        son = f"durum {durum}"
    raise BistErisimHatasi(f"{url} alınamadı ({deneme} deneme), son: {son}")
