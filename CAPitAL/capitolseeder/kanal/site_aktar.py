"""Rasathane sitesi için CAPitAL beyan tablosu: `site-veri/capital/beyanlar.json`.

Yalnız kayıtlı beyanları yazar; Telegram ya da gönderim yoktur. Kaynağı beyan CSV'sinden okur,
ortak yazıcıyla (rasathane_ortak.site) şemalı JSON üretir. Kaynakta bileşik "uyum skoru" yoktur;
bunun yerine kaynağın geç bayrağı ve işlemden bildirime geçen gün sayısı gösterilir.
"""

from __future__ import annotations

import argparse
import datetime
import logging
from pathlib import Path
from typing import Optional

from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz

from capitolseeder.kanal.arsiv import beyanlari_oku
from capitolseeder.kanal.model import Beyan

logger = logging.getLogger("capitolseeder.kanal.site")

BOLUM = "capital"
SAYFA = "beyanlar"
BASLIK = "Kongre işlemleri"
ACIKLAMA = (
    "Kongre üyelerinin kamuya açık işlem beyanları, en yeni bildirim üstte. "
    "Tutarlar yasal aralıktır, kesin değer değildir. Bir beyan tek başına hukuki ihlal "
    "ya da yatırım kararı anlamına gelmez."
)
_KAYNAKLAR = (
    Kaynak("House Clerk finansal beyanlar", "https://disclosures-clerk.house.gov/"),
    Kaynak("Senato eFD arama", "https://efdsearch.senate.gov/"),
    Kaynak("Kadoa congress-trading-monitor", "https://github.com/kadoa-org/congress-trading-monitor"),
)
_PARTI = {"D": "Demokrat", "R": "Cumhuriyetçi", "I": "Bağımsız"}
_ISLEM = {"Purchase": "Alış", "Sale (Full)": "Satış", "Sale (Partial)": "Satış", "Exchange": "Değişim"}
_SUTUNLAR = (
    Sutun("bildirim", "Bildirim tarihi", "tarih"),
    Sutun("uye", "Üye", "metin"),
    Sutun("parti", "Parti", "metin"),
    Sutun("meclis", "Meclis", "metin"),
    Sutun("varlik", "Varlık", "metin"),
    Sutun("islem", "İşlem", "metin"),
    Sutun("tutar", "Tutar aralığı", "metin"),
    Sutun("uyum", "Süre uyumu", "metin"),
    Sutun("gecikme", "İşlemden bildirime (gün)", "sayi", 0),
    Sutun("belge", "Belge", "metin"),
)


def _varlik(b: Beyan) -> str:
    if b.ticker:
        return b.ticker
    ad = " ".join(b.varlik.split())
    return ad[:60].rstrip() + ("…" if len(ad) > 60 else "")


def satir(b: Beyan) -> dict[str, object]:
    return {
        "bildirim": b.beyan_tarihi.isoformat(),
        "uye": b.uye,
        "parti": _PARTI.get(b.parti, b.parti),
        "meclis": b.meclis,
        "varlik": _varlik(b),
        "islem": _ISLEM.get(b.islem, b.islem),
        "tutar": b.tutar_etiket,
        "uyum": "Geç" if b.gec else "Zamanında",
        "gecikme": b.gecikme,
        "belge": b.belge,
    }


def site_aktar(kok: Path, simdi: datetime.datetime, beyanlar: list[Beyan]) -> Optional[Path]:
    """`kok / "capital" / "beyanlar.json"` yazar. Beyan yoksa eski dosyaya dokunmaz."""
    if not beyanlar:
        logger.warning("Beyan yok; site verisi yazılmadı, eski dosya korunur.")
        return None
    sirali = sorted(beyanlar, key=lambda b: (b.beyan_tarihi, b.islem_tarihi, b.uye), reverse=True)
    return sayfa_yaz(
        kok,
        BOLUM,
        SAYFA,
        baslik=BASLIK,
        aciklama=ACIKLAMA,
        guncellendi=simdi,
        kaynaklar=_KAYNAKLAR,
        sutunlar=_SUTUNLAR,
        satirlar=[satir(b) for b in sirali],
        suzgecler=("parti", "islem", "uyum"),
        grafik="yok",
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m capitolseeder.kanal.site_aktar",
        description="CAPitAL beyan arşivinden Rasathane site verisi (yalnız dosya yazar, gönderim yok)",
    )
    ap.add_argument("--veri", type=Path, default=Path("kanal/veri"), help="beyanlar.csv klasörü")
    ap.add_argument("--kok", type=Path, required=True, help="site-veri kökü (ör. rasathane/site-veri)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    yol = site_aktar(a.kok, datetime.datetime.now(datetime.timezone.utc), beyanlari_oku(a.veri / "beyanlar.csv"))
    if yol is not None:
        print(yol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
