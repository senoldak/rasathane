"""Site verisi: kanal kaydındaki SEC Form 4 işlemleri ve 0–100 puanı `site-veri/inseeder/` altına yazar.

Çıktı tek sayfa (`islemler.json`) ve seri dosyası yoktur: kayıtta hisse fiyat geçmişi tutulmaz,
bu yüzden sayfa "grafik yok" olarak işaretlenir.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from inseeder.engine.scorer import compute_conviction_score
from inseeder.kanal.kayit import Kayit
from inseeder.kanal.model import UNVAN_TR, Beyan
from inseeder.kanal.secim import alim_mi, kanala_uygun
from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz

BOLUM = "inseeder"
SAYFA = "islemler"
BASLIK = "Yönetici işlemleri"
ACIKLAMA = (
    "SEC Form 4 beyanlarından: en az $100 bin açık piyasa alımı ve plan dışı CEO/CFO satışları (≥ $5 Mn). "
    "Puan 0–100: rol, tutar, pozisyon artışı, 7 günlük küme ve plan dışı durumu. "
    "Grafik yok: hisse fiyat geçmişi bu sayfada yok."
)
KAYNAK = Kaynak("SEC EDGAR", "https://www.sec.gov/")
KUME_GUN = 7
EN_UNVAN = {tr: en for en, tr in UNVAN_TR.items()}
SUTUNLAR = [
    Sutun("tarih", "Bildirim tarihi", "tarih"),
    Sutun("hisse", "Hisse", "metin"),
    Sutun("sirket", "Şirket", "metin"),
    Sutun("rol", "Rol", "metin"),
    Sutun("islem", "İşlem", "metin"),
    Sutun("tutar", "Tutar (USD)", "sayi", 0),
    Sutun("puan", "Puan", "sayi", 0),
]


def _kume_sayisi(beyanlar: List[Beyan], b: Beyan) -> int:
    """Aynı hissede, işlemin dosyalandığı gün ve önceki 6 günde alım yapan farklı kişi sayısı."""
    ilk = b.dosyalama_gunu - timedelta(days=KUME_GUN - 1)
    return len({
        x.kisi for x in beyanlar
        if alim_mi(x) and x.sembol == b.sembol and ilk <= x.dosyalama_gunu <= b.dosyalama_gunu
    })


def puan(b: Beyan, kume_sayisi: int) -> int:
    """Depodaki puan modeli (engine/scorer.py), kanal kaydındaki rol metninden beslenir."""
    rol = EN_UNVAN.get(b.unvan, "Other")
    return compute_conviction_score({
        "transaction_code": b.kod,
        "insider_title": rol,
        "is_officer": rol == "Officer",
        "is_director": rol == "Director",
        "is_ten_percent": rol == "10% Owner",
        "value": b.tutar,
        "shares": b.adet,
        "shares_owned_after": b.sonraki_pay or 0.0,
        "is_10b5_1": b.plan_10b5_1,
    }, kume_sayisi)["score"]


def _tekil(beyanlar: List[Beyan]) -> List[Beyan]:
    """Form 4 çok kişili bildirimde aynı işlemi tekrarlayabilir; ilk beyan tutulur."""
    tekil: Dict[Tuple, Beyan] = {}
    for b in beyanlar:
        anahtar = (b.sembol, b.dosyalama_gunu, b.kod, b.adet, round(b.ort_fiyat, 4))
        tekil.setdefault(anahtar, b)
    return list(tekil.values())


def satirlar(beyanlar: List[Beyan]) -> List[dict]:
    uygun = _tekil([b for b in beyanlar if kanala_uygun(b)])
    sonuc = [
        {
            "tarih": b.dosyalama_gunu.isoformat(),
            "hisse": b.sembol,
            "sirket": b.sirket,
            "rol": b.unvan,
            "islem": "Alım" if b.kod == "P" else "Satış",
            "tutar": b.tutar,
            "puan": puan(b, _kume_sayisi(uygun, b)),
        }
        for b in uygun
    ]
    sonuc.sort(key=lambda r: (r["tarih"], r["tutar"]), reverse=True)
    return sonuc


def aktar(kok: Path, simdi: datetime, beyanlar: List[Beyan]) -> Path:
    """`kok / "inseeder" / "islemler.json"` yazar ve yolunu döndürür."""
    return sayfa_yaz(
        Path(kok),
        BOLUM,
        SAYFA,
        baslik=BASLIK,
        aciklama=ACIKLAMA,
        guncellendi=simdi,
        kaynaklar=[KAYNAK],
        sutunlar=SUTUNLAR,
        satirlar=satirlar(beyanlar),
        suzgecler=["islem", "rol"],
        grafik="yok",
    )


def _argumanlar(argv: Optional[List[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m inseeder.kanal.site_aktar",
                                description="INseeder kanal kaydından Rasathane site verisi")
    p.add_argument("--veri", type=Path, default=Path("kanal_veri"), help="beyanlar.csv klasörü")
    p.add_argument("--kok", type=Path, default=Path("../site-veri"), help="Rasathane site-veri kökü")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    arg = _argumanlar(argv)
    beyanlar = Kayit(arg.veri).beyanlar()
    yol = aktar(arg.kok, datetime.now(timezone.utc), beyanlar)
    print(f"[inseeder] site verisi: {yol} ({len(satirlar(beyanlar))} işlem)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
