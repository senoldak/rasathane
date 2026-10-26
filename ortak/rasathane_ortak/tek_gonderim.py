"""Rasathane kartlarını Telegram'a tek tek (sendPhoto) gönderir; her gönderimi kart düzeyinde kaydeder."""

from __future__ import annotations

import csv
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Istek = Callable[
    [str, dict[str, str], dict[str, tuple[str, bytes, str]]], tuple[int, dict[str, Any]]
]

AZAMI_DENEME = 3
_ALANLAR = ["gun", "kart", "sayfa", "mesaj_id"]


class GonderimHatasi(Exception):
    pass


def hedef_coz(hedef: str) -> tuple[str, int | None]:
    """'@grup:5' → ('@grup', 5); konusuz hedef → (hedef, None)."""
    sohbet, ayrac, konu = hedef.strip().rpartition(":")
    if not ayrac:
        return hedef.strip(), None
    if not konu.isdigit():
        raise ValueError(f"Konu numarası sayı olmalı: {hedef!r}")
    return sohbet, int(konu)


@dataclass(frozen=True)
class Giden:
    kart: str
    sayfa: int
    png: bytes
    aciklama: str


class GonderimKaydi:
    """gonderilen_kartlar.csv: gun,kart,sayfa,mesaj_id. Her satır gönderimden hemen sonra diske eklenir."""

    def __init__(self, yol: Path) -> None:
        self.yol = Path(yol)
        self._gidenler: set[tuple[str, str, int]] = set()
        if self.yol.exists():
            with open(self.yol, encoding="utf-8", newline="") as f:
                for s in csv.DictReader(f):
                    self._gidenler.add((s["gun"], s["kart"], int(s["sayfa"])))

    def gonderildi_mi(self, gun: str, kart: str, sayfa: int) -> bool:
        return (gun, kart, sayfa) in self._gidenler

    def ekle(self, gun: str, kart: str, sayfa: int, mesaj_id: int) -> None:
        yeni = not self.yol.exists()
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        with open(self.yol, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if yeni:
                w.writerow(_ALANLAR)
            w.writerow([gun, kart, sayfa, mesaj_id])
        self._gidenler.add((gun, kart, sayfa))


def foto_gonder(
    istek: Istek,
    token: str,
    hedef: str,
    png: bytes,
    aciklama: str,
    uyku: Callable[[float], None] = time.sleep,
    azami_bekleme: float = 120.0,
) -> int:
    sohbet, konu = hedef_coz(hedef)
    alanlar = {"chat_id": sohbet, "caption": aciklama}
    if konu is not None:
        alanlar["message_thread_id"] = str(konu)
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    beklenen = 0.0
    for _ in range(AZAMI_DENEME):
        try:
            durum, govde = istek(url, alanlar, {"photo": ("kart.png", png, "image/png")})
        except Exception as e:  # ağ hatası: mesajında URL (dolayısıyla anahtar) olabilir
            raise GonderimHatasi(
                f"sendPhoto isteği başarısız: {type(e).__name__}: {str(e).replace(token, '***')}"
            ) from None
        if durum == 429:
            bekle = float((govde.get("parameters") or {}).get("retry_after", 5))
            if beklenen + bekle > azami_bekleme:
                raise GonderimHatasi(
                    f"Telegram hız sınırı: {bekle:.0f} sn bekleme istendi, sınır aşılıyor"
                )
            beklenen += bekle
            uyku(bekle)
            continue
        if not (200 <= durum < 300) or not govde.get("ok"):
            aciklama_ = str(govde.get("description", f"HTTP {durum}")).replace(token, "***")
            raise GonderimHatasi(f"sendPhoto başarısız: {aciklama_}")
        return int(govde["result"]["message_id"])
    raise GonderimHatasi("Telegram hız sınırı: üç denemede de 429 alındı")


def sirayla_gonder(
    istek: Istek,
    token: str,
    hedef: str,
    gun: str,
    gidenler: Sequence[Giden],
    kayit: GonderimKaydi,
    uyku: Callable[[float], None] = time.sleep,
    ara: float = 1.5,
    sonrasi: Callable[[Giden, int], None] | None = None,
) -> list[int]:
    """Kartları sırayla gönderir; kayıtta olanı atlar, ilk kalıcı hatada durur (GonderimHatasi)."""
    kimlikler: list[int] = []
    for giden in gidenler:
        if kayit.gonderildi_mi(gun, giden.kart, giden.sayfa):
            continue
        if kimlikler:
            uyku(ara)
        mid = foto_gonder(istek, token, hedef, giden.png, giden.aciklama, uyku=uyku)
        kayit.ekle(gun, giden.kart, giden.sayfa, mid)
        if sonrasi:
            sonrasi(giden, mid)
        kimlikler.append(mid)
    return kimlikler
