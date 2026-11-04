"""Rasathane sitesi için botun kartlarının verisi: günlük, haftalık, performans ve gecikme.

Seçim ve hesap kuralları botla aynıdır (secim.py, performans.py, grafik.py). Çıktılar
`site-veri/capital/seri/ozet-*.json` dosyalarıdır; `seri/` alt klasörü sayfa listesine girmez.
Fiyat gerektiren iki bölüm (performans, gecikme) yalnız `--fiyat` ile yazılır: fiyatlar Yahoo'dan
çekilir, testlerde sahte fiyat verilir.
"""

from __future__ import annotations

import argparse
import bisect
import datetime
import logging
import re
from pathlib import Path
from typing import Optional

from rasathane_ortak.site import _yaz

from capitolseeder.kanal.arsiv import beyanlari_oku
from capitolseeder.kanal.grafik import GUN_SAYISI, gecikme_secimi
from capitolseeder.kanal.model import Beyan, hisse_mi, kisa_sirket, kisa_tutar
from capitolseeder.kanal.performans import (
    KARSILASTIRMA,
    FiyatHatasi,
    Fiyatlar,
    fiyatlari_cek,
    pencere_baslangici,
    UyePerformansi,
    performans,
)
from capitolseeder.kanal.secim import gunluk, haftalik
from capitolseeder.kanal.site_aktar import _ISLEM, _PARTI

logger = logging.getLogger("capitolseeder.kanal.site")

BOLUM = "capital"
KLASOR = "seri"


def _gun_beyanlari(beyanlar: list[Beyan]) -> tuple[datetime.date, list[Beyan]]:
    gun = max(b.beyan_tarihi for b in beyanlar)
    return gun, [b for b in beyanlar if b.beyan_tarihi == gun]


def _uye(b: Beyan) -> dict[str, object]:
    return {"uye": b.uye, "parti": _PARTI.get(b.parti, b.parti), "eyalet": b.eyalet}


def gunluk_ozeti(beyanlar: list[Beyan]) -> Optional[dict[str, object]]:
    """Son beyan gününün en büyük alımları (botun günlük kartı, üye başı en çok 3)."""
    gun, gunku = _gun_beyanlari(beyanlar)
    hisseler = [b for b in gunku if hisse_mi(b)]
    secilen = gunluk(gunku)
    if not secilen:
        return None
    return {
        "tarih": gun.isoformat(),
        "toplam": len(hisseler),
        "uye": len({b.uye for b in hisseler}),
        "satirlar": [
            {
                **_uye(b),
                "ticker": b.ticker,
                "varlik": kisa_sirket(b.varlik, 40),
                "islem": _ISLEM.get(b.islem, b.islem),
                "tutar": b.tutar_etiket,
                "gecikme": b.gecikme,
                "gec": b.gec,
            }
            for b in secilen
        ],
    }


def haftalik_ozeti(beyanlar: list[Beyan]) -> Optional[dict[str, object]]:
    """Son beyan gününü içeren pazartesi–cuma haftasının en çok üyenin işlem yaptığı hisseleri."""
    gun, _ = _gun_beyanlari(beyanlar)
    pazartesi = gun - datetime.timedelta(days=gun.weekday())
    ozet = haftalik(beyanlar, pazartesi, alan="beyan_tarihi")
    if not ozet:
        return None
    return {
        "baslangic": pazartesi.isoformat(),
        "bitis": (pazartesi + datetime.timedelta(days=4)).isoformat(),
        "satirlar": [
            {
                "ticker": o.ticker,
                "varlik": kisa_sirket(o.varlik, 40),
                "alan": len(o.alan_uyeler),
                "satan": len(o.satan_uyeler),
                "partiler": ", ".join(f"{_PARTI.get(p, p)} {n}" for p, n in sorted(o.partiler.items())),
                "tutar": kisa_tutar(o.tutar_alt, o.tutar_ust),
                "iki_parti": o.iki_parti_alim,
            }
            for o in ozet
        ],
    }


def performans_ozeti(beyanlar: list[Beyan], fiyatlar: Fiyatlar, bugun: datetime.date) -> Optional[dict[str, object]]:
    """Beyan edilen alımların işlemden bugüne SPY'ye göre farkı; en yüksek ve en düşük beşer üye."""
    try:
        ust, alt, baslangic = performans(beyanlar, fiyatlar, bugun)
    except FiyatHatasi as e:
        logger.warning("Performans bölümü atlandı: %s", e)
        return None

    def satir(p: UyePerformansi) -> dict[str, object]:
        return {
            "uye": p.uye,
            "parti": _PARTI.get(p.parti, p.parti),
            "eyalet": p.eyalet,
            "alim": p.alim_sayisi,
            "ort_degisim": round(p.ort_degisim, 2),
            "ort_spy": round(p.ort_spy, 2),
            "fark": round(p.fark, 2),
        }

    return {
        "baslangic": baslangic.isoformat(),
        "bugun": bugun.isoformat(),
        "en_yuksek": [satir(p) for p in ust[:5]],
        "en_dusuk": [satir(p) for p in alt[:5]],
    }


def gecikme_ozeti(beyanlar: list[Beyan], fiyatlar: Fiyatlar, bugun: datetime.date) -> Optional[dict[str, object]]:
    """Son beyan gününün seçilen alımı: hissenin ve S&P 500'ün (ilk değere ölçekli) seyri."""
    _, gunku = _gun_beyanlari(beyanlar)
    b = gecikme_secimi(gunku)
    if b is None:
        return None
    kapanis = fiyatlar.get(b.ticker)
    spy = fiyatlar.get(KARSILASTIRMA)
    if not kapanis or not spy:
        logger.warning("Gecikme bölümü atlandı: %s ya da SPY fiyatı yok", b.ticker)
        return None
    bas = min(bugun - datetime.timedelta(days=GUN_SAYISI), b.islem_tarihi - datetime.timedelta(days=7))
    seri = [(g, v) for g, v in kapanis if bas <= g <= bugun]
    if len(seri) < 2:
        return None
    spy_gunleri = [g for g, _ in spy]
    spy_degeri = dict(spy)
    def spy_on(g: datetime.date) -> float:
        i = bisect.bisect_right(spy_gunleri, g) - 1
        return spy_degeri[spy_gunleri[max(i, 0)]]

    olcek = seri[0][1] / spy_on(seri[0][0])
    return {
        **_uye(b),
        "ticker": b.ticker,
        "varlik": kisa_sirket(b.varlik, 40),
        "islem_tarihi": b.islem_tarihi.isoformat(),
        "beyan_tarihi": b.beyan_tarihi.isoformat(),
        "tutar": b.tutar_etiket,
        "gecikme": b.gecikme,
        "tarihler": [g.isoformat() for g, _ in seri],
        "hisse": [round(v, 4) for _, v in seri],
        "spy": [round(spy_on(g) * olcek, 4) for g, _ in seri],
    }


HISSE_KODU = re.compile(r"^[A-Za-z0-9.]{1,10}$")


def hisse_fiyat_verisi(beyanlar: list[Beyan], fiyatlar: Fiyatlar, simdi: datetime.datetime) -> dict[str, dict[str, object]]:
    """Beyanlarda geçen her hisse için kapanış serisi; fiyatı gelmeyenler atlanır."""
    kodlar = sorted({b.ticker for b in beyanlar if hisse_mi(b) and HISSE_KODU.fullmatch(b.ticker)})
    sonuc: dict[str, dict[str, object]] = {}
    for kod in kodlar:
        seri = fiyatlar.get(kod)
        if not seri:
            continue
        sonuc[kod] = {
            "sema": 1,
            "ticker": kod,
            "guncellendi": simdi.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tarihler": [g.isoformat() for g, _ in seri],
            "kapanis": [round(v, 4) for _, v in seri],
        }
    return sonuc


def fiyat_ihtiyaci(beyanlar: list[Beyan], bugun: datetime.date) -> tuple[set[str], datetime.date]:
    """Sayfanın ve bölümlerin istediği semboller ve en eski başlangıç."""
    baslangic = pencere_baslangici(beyanlar, bugun)
    alimlar = [b for b in beyanlar if b.yon == "Alış" and hisse_mi(b) and b.beyan_tarihi >= baslangic]
    tum_hisseler = [b for b in beyanlar if hisse_mi(b) and HISSE_KODU.fullmatch(b.ticker)]
    semboller = {b.ticker for b in alimlar} | {b.ticker for b in tum_hisseler} | {KARSILASTIRMA}
    en_eski = min((b.islem_tarihi for b in alimlar), default=baslangic)
    if tum_hisseler:
        en_eski = min(en_eski, min(b.islem_tarihi for b in tum_hisseler) - datetime.timedelta(days=7))
    _, gunku = _gun_beyanlari(beyanlar)
    b = gecikme_secimi(gunku)
    if b is not None:
        semboller.add(b.ticker)
        en_eski = min(en_eski, b.islem_tarihi - datetime.timedelta(days=7), bugun - datetime.timedelta(days=GUN_SAYISI))
    return semboller, en_eski


def yaz(
    kok: Path,
    simdi: datetime.datetime,
    beyanlar: list[Beyan],
    fiyatlar: Optional[Fiyatlar] = None,
) -> list[Path]:
    """Özet dosyalarını yazar. Veri yoksa ya da bölüm üretilemezse eski dosya korunur."""
    if not beyanlar:
        return []
    bugun = simdi.date()
    bolumler: list[tuple[str, Optional[dict[str, object]]]] = [
        ("gunluk", gunluk_ozeti(beyanlar)),
        ("haftalik", haftalik_ozeti(beyanlar)),
    ]
    if fiyatlar is not None:
        bolumler += [
            ("performans", performans_ozeti(beyanlar, fiyatlar, bugun)),
            ("gecikme", gecikme_ozeti(beyanlar, fiyatlar, bugun)),
        ]
    yollar: list[Path] = []
    if fiyatlar is not None:
        for kod, veri in hisse_fiyat_verisi(beyanlar, fiyatlar, simdi).items():
            yollar.append(_yaz(Path(kok) / BOLUM / KLASOR / f"hisse-{kod}.json", veri))
    for ad, veri in bolumler:
        if veri is None:
            continue
        veri = {"sema": 1, "guncellendi": simdi.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **veri}
        yollar.append(_yaz(Path(kok) / BOLUM / KLASOR / f"ozet-{ad}.json", veri))
    return yollar


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m capitolseeder.kanal.site_ozet",
        description="CAPitAL kartlarının site verisi (günlük, haftalık; --fiyat ile performans ve gecikme)",
    )
    ap.add_argument("--veri", type=Path, default=Path("kanal/veri"), help="beyanlar.csv klasörü")
    ap.add_argument("--kok", type=Path, required=True, help="site-veri kökü")
    ap.add_argument("--fiyat", action="store_true", help="performans ve gecikme için Yahoo fiyatlarını çek")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    simdi = datetime.datetime.now(datetime.timezone.utc)
    beyanlar = beyanlari_oku(a.veri / "beyanlar.csv")
    fiyatlar: Optional[Fiyatlar] = None
    if a.fiyat and beyanlar:
        semboller, baslangic = fiyat_ihtiyaci(beyanlar, simdi.date())
        fiyatlar = fiyatlari_cek(sorted(semboller), baslangic)
    for yol in yaz(a.kok, simdi, beyanlar, fiyatlar):
        print(yol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
