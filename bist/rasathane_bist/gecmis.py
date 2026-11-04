"""VİOP günlük özetlerinin birikimi: dayanak başına toplamlar, vadeli uzlaşma geçmişi.

Dosya `bist/veri/viop-gunluk.json`: `{"2026-10-30": {"dayanak": {...}, "uzlasma": {...}}, ...}`.
Tatil ya da yayımlanmamış gün `null` olarak işaretlenir; böylece her koşu aynı günü yeniden çekmez.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from .indir import BistErisimHatasi, Indirici, dosya_al
from .viop import (
    ViopSatiri,
    dayanak_kanonik,
    opsiyon_kodu_coz,
    opsiyon_mu,
    vadeli_mi,
    viop_bulteni_oku,
    viop_bulteni_url,
)

log = logging.getLogger("viop")

GECMIS_GUN = 420  # ~290 işlem günü: EMA 233 ve haftalık RSI için yeterli geçmiş
_ALANLAR = ("vadeli_hacim", "vadeli_acik", "cagri_hacim", "put_hacim", "cagri_acik", "put_acik")

Gecmis = dict[str, dict[str, Any] | None]


def _bos() -> dict[str, float]:
    return {a: 0.0 for a in _ALANLAR}


def gun_ozeti(satirlar: list[ViopSatiri]) -> dict[str, Any]:
    """Bir günün bülteninden dayanak toplamları, ön vade uzlaşması ve vadeli uzlaşmalar.

    Ön vade: dayanağın en çok işlem gören vadeli sözleşmesi (kodu ve uzlaşması). Vadeli uzlaşmalar
    kod başına tutulur; ön vade değişince (vade yuvarlanınca) seriyi düzeltmek için gerekir.
    """
    dayanaklar: dict[str, dict[str, float]] = {}
    kodlar: dict[str, str] = {}
    uzlasma: dict[str, float] = {}
    on: dict[str, tuple[float, float, str]] = {}
    for s in satirlar:
        if vadeli_mi(s):
            d = dayanak_kanonik(s)
            e = dayanaklar.setdefault(d, _bos())
            e["vadeli_hacim"] += s.hacim_tl
            e["vadeli_acik"] += s.acik_pozisyon
            uzlasma[s.kod] = s.uzlasma
            if s.uzlasma > 0 and s.hacim_tl > on.get(d, (-1.0, 0.0, ""))[0]:
                on[d] = (s.hacim_tl, s.uzlasma, s.kod)
        elif opsiyon_mu(s):
            c = opsiyon_kodu_coz(s.kod)
            if c is None:
                continue
            e = dayanaklar.setdefault(c.dayanak, _bos())
            tur = "cagri" if c.tur == "C" else "put"
            e[f"{tur}_hacim"] += s.hacim_tl
            e[f"{tur}_acik"] += s.acik_pozisyon
    for d, (_, fiyat, kod) in on.items():
        dayanaklar[d]["on_uzlasma"] = fiyat
        kodlar[d] = kod
    return {"dayanak": dayanaklar, "on_kod": kodlar, "uzlasma": uzlasma}


def gecmis_oku(yol: Path) -> Gecmis:
    if not yol.exists():
        return {}
    return cast(Gecmis, json.loads(yol.read_text("utf-8")))


def gecmis_yaz(yol: Path, gecmis: Gecmis) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".tmp")
    gecici.write_text(json.dumps(gecmis, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    gecici.replace(yol)


def geri_doldur(gecmis: Gecmis, bugun: date, indir: Indirici, gun_sayisi: int = GECMIS_GUN) -> int:
    """`bugun`den geriye eksik iş günlerini indirir. Dönüş: yeni eklenen gün sayısı."""
    eklenen = 0
    for n in range(gun_sayisi):
        gun = bugun - timedelta(days=n)
        anahtar = gun.isoformat()
        if gun.weekday() >= 5 or anahtar in gecmis:
            continue
        try:
            bayt = dosya_al(indir, viop_bulteni_url(gun))
        except BistErisimHatasi as hata:
            log.warning("VİOP geçmişi %s alınamadı, sonraki koşuda denenir: %s", gun, hata)
            continue
        if bayt is None:
            # Bugünkü bülten henüz yayımlanmamış olabilir: onu tatil saymayız, sonraki koşu bakar.
            if n:
                gecmis[anahtar] = None
            continue
        bulten_gunu, satirlar = viop_bulteni_oku(bayt)
        gecmis[bulten_gunu.isoformat()] = gun_ozeti(satirlar)
        eklenen += 1
    return eklenen


def gunler(gecmis: Gecmis, son: date) -> list[str]:
    """`son` gününe kadar (dahil) özeti olan günler, eskiden yeniye."""
    return sorted(k for k, v in gecmis.items() if v is not None and k <= son.isoformat())
