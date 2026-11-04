"""VİOP gün sonu bülteninden site verisi: `site-veri/viop/` altında vadeli ve opsiyon sayfaları.

Değişim yüzdesi bültendeki gibi yüzde birimindedir (-1,48 = %-1,48). Grafik yok: geçmiş seri
henüz biriktirilmiyor.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz

from .viop import ViopSatiri, dayanak_kanonik, vadeli_mi

BOLUM = "viop"
_BIST = Kaynak("Borsa İstanbul", "https://borsaistanbul.com/")

VADELI_SUTUNLAR = (
    Sutun("kod", "Kod", "metin"),
    Sutun("ad", "Sözleşme", "metin"),
    Sutun("dayanak", "Dayanak", "metin"),
    Sutun("vade", "Vade", "tarih"),
    Sutun("uzlasma", "Uzlaşma", "sayi", 2),
    Sutun("degisim", "Değişim", "yuzde", 2),
    Sutun("hacim", "Hacim (TL)", "sayi", 0),
    Sutun("acik", "Açık pozisyon", "sayi", 0),
    Sutun("acik_degisim", "Açık poz. değişimi", "sayi", 0),
)


def _vadeli_satiri(s: ViopSatiri) -> dict[str, object]:
    return {
        "kod": s.kod,
        "ad": s.ad,
        "dayanak": dayanak_kanonik(s),
        "vade": s.vade.isoformat(),
        "uzlasma": s.uzlasma,
        "degisim": s.uzlasma_degisim_yuzde / 100,
        "hacim": s.hacim_tl,
        "acik": s.acik_pozisyon,
        "acik_degisim": s.acik_pozisyon_degisimi,
    }


def aktar(kok: Path, gun: date, satirlar: list[ViopSatiri], simdi: datetime) -> list[Path]:
    """VİOP bölümünün vadeli sayfasını yazar (hacme göre sıralı).

    Opsiyonlar ayrı Opsiyon bölümündedir; VİOP sayfası onları yayımlamaz.
    """
    aciklama = f"{gun:%d.%m.%Y} tarihli gün sonu bülteni. Kaynak: Borsa İstanbul."
    vadeliler = sorted((s for s in satirlar if vadeli_mi(s)), key=lambda s: -s.hacim_tl)
    return [
        sayfa_yaz(
            kok,
            BOLUM,
            "vadeli",
            baslik="Vadeli işlemler",
            aciklama=aciklama,
            guncellendi=simdi,
            kaynaklar=[_BIST],
            sutunlar=VADELI_SUTUNLAR,
            satirlar=[_vadeli_satiri(s) for s in vadeliler],
            suzgecler=("dayanak",),
            grafik="yok",
        ),
    ]
