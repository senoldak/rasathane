"""Rasathane site JSON yazıcısı: sayfa ve seri dosyalarını şemalı yazar."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

SEMA = 1

_AD = re.compile(r"^[a-z0-9-]{1,40}$")
_SERI = re.compile(r"^[A-Za-z0-9=._^-]{1,40}$")


@dataclass(frozen=True)
class Sutun:
    anahtar: str
    baslik: str
    tur: Literal["metin", "sayi", "yuzde", "tarih"]
    basamak: int = 2


@dataclass(frozen=True)
class Kaynak:
    ad: str
    url: str


def _ad_denetle(deger: str, ne: str) -> None:
    if not _AD.fullmatch(deger):
        raise ValueError(f"Geçersiz {ne} adı: {deger!r}")


def _temiz(deger: object) -> object:
    if isinstance(deger, float) and not math.isfinite(deger):
        return None
    return deger


def _yaz(yol: Path, veri: object) -> Path:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".tmp")
    metin = json.dumps(
        veri, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=1
    )
    gecici.write_text(metin + "\n", encoding="utf-8")
    os.replace(gecici, yol)
    return yol


def sayfa_yaz(
    kok: Path,
    bolum: str,
    sayfa: str,
    *,
    baslik: str,
    aciklama: str,
    guncellendi: datetime,
    kaynaklar: Sequence[Kaynak],
    sutunlar: Sequence[Sutun],
    satirlar: Sequence[Mapping[str, object]],
    suzgecler: Sequence[str] = (),
    grafik: Literal["cizgi", "yok"] = "cizgi",
) -> Path:
    _ad_denetle(bolum, "bölüm")
    _ad_denetle(sayfa, "sayfa")
    izinli = {s.anahtar for s in sutunlar} | {"seri"}
    temiz_satirlar = []
    for satir in satirlar:
        fazla = set(satir) - izinli
        if fazla:
            raise ValueError(f"Sütunda olmayan anahtar: {sorted(fazla)}")
        temiz_satirlar.append({k: _temiz(v) for k, v in satir.items()})
    veri = {
        "sema": SEMA,
        "bolum": bolum,
        "sayfa": sayfa,
        "baslik": baslik,
        "aciklama": aciklama,
        "guncellendi": guncellendi.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "kaynaklar": [{"ad": k.ad, "url": k.url} for k in kaynaklar],
        "sutunlar": [
            {
                "anahtar": s.anahtar,
                "baslik": s.baslik,
                "tur": s.tur,
                "basamak": s.basamak,
            }
            for s in sutunlar
        ],
        "suzgecler": list(suzgecler),
        "grafik": grafik,
        "satirlar": temiz_satirlar,
    }
    return _yaz(Path(kok) / bolum / f"{sayfa}.json", veri)


def seri_yaz(
    kok: Path,
    bolum: str,
    anahtar: str,
    noktalar: Sequence[tuple[date, float]],
    *,
    ad: str,
    birim: str,
    isaretler: Sequence[tuple[date, str]] = (),
) -> Path:
    _ad_denetle(bolum, "bölüm")
    if anahtar == ".." or not _SERI.fullmatch(anahtar):
        raise ValueError(f"Geçersiz seri anahtarı: {anahtar!r}")
    veri = {
        "sema": SEMA,
        "ad": ad,
        "birim": birim,
        "noktalar": [[g.isoformat(), d] for g, d in noktalar if _temiz(d) is not None],
        "isaretler": [[g.isoformat(), m] for g, m in isaretler],
    }
    return _yaz(Path(kok) / bolum / "seri" / f"{anahtar}.json", veri)
