"""INseeder kartları: veriyi Rasathane'nin ortak Kâğıt kartına çevirir."""
from datetime import date
from typing import List

from inseeder.kanal.bicim import fiyat, para, yuzde
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Bolum, Hucre, Kart
from rasathane_ortak.kagit import Satir as KartSatiri
from inseeder.kanal.secim import HaftalikOzet, Satir

FIKIR = "INseeder"
KAYNAK = "SEC EDGAR"
GUNLUK_AD = "İçeriden Alımlar"
HAFTALIK_AD = "Haftanın Özeti"
GUNLUK_ACIKLAMA = "SEC'e bildirilen açık piyasa alımları · ≥ $100 bin · 10b5-1 planı dışı"
HAFTALIK_ACIKLAMA = "SEC'e bildirilen Form 4 beyanlarından haftanın öne çıkanları"
KUME_BOLUMU = "Haftanın kümeleri · birden çok yöneticinin alımı"
SATIS_BOLUMU = "Haftanın büyük satışları · CEO/CFO, plan dışı, ≥ $5 Mn"

# Sol alt yazı için yaklaşık genişlik: tek sağ sütunlu kartta tutar sütunundan kalan alan.
SOL_GENISLIK = 640


def sirket_unvan(sirket: str, unvan: str) -> str:
    """Satırın alt yazısı: unvan hep görünür, sığmazsa şirket adı kısaltılır."""
    ek = f" · {unvan}"
    f = kagit.font(28)
    return kagit._kisalt(sirket, f, SOL_GENISLIK - f.getlength(ek)) + ek


def _degisim_metni(degisim) -> str:
    if degisim == "yeni":
        return "yeni pozisyon"
    if isinstance(degisim, float):
        return yuzde(degisim)
    return ""


def gunluk_kart(gun: date, satirlar: List[Satir]) -> Kart:
    return Kart(
        fikir=FIKIR, ad=GUNLUK_AD, tarih=kagit.tarih_metni(gun), alt_baslik=GUNLUK_ACIKLAMA, kaynak=KAYNAK,
        satirlar=tuple(
            KartSatiri(ust=s.beyan.sembol, alt=sirket_unvan(s.beyan.sirket, s.beyan.unvan),
                       sag=(Hucre(para(s.beyan.tutar), kalin=True,
                                  alt="küme" if s.kume else _degisim_metni(s.degisim), alt_vurgu=s.kume),))
            for s in satirlar),
    )


def haftalik_kart(ozet: HaftalikOzet) -> Kart:
    ogeler: list = [Bolum(KUME_BOLUMU)]
    if not ozet.kumeler:
        ogeler.append(KartSatiri(ust="—", alt="Bu hafta birden çok yöneticinin alım bildirdiği şirket yok."))
    for k in ozet.kumeler:
        ogeler.append(KartSatiri(ust=k.sembol, alt=k.sirket,
                                 sag=(Hucre(para(k.toplam), kalin=True, alt=f"{k.kisi_sayisi} kişi", alt_vurgu=True),)))
    ogeler.append(Bolum(SATIS_BOLUMU))
    if not ozet.satislar:
        ogeler.append(KartSatiri(ust="—", alt="Bu hafta eşiği geçen satış yok."))
    for b in ozet.satislar:
        ogeler.append(KartSatiri(ust=b.sembol, alt=sirket_unvan(b.sirket, b.unvan),
                                 sag=(Hucre(para(b.tutar), kalin=True, alt=f"@ {fiyat(b.ort_fiyat)}"),)))
    return Kart(fikir=FIKIR, ad=HAFTALIK_AD, tarih=kagit.aralik_metni(ozet.gunler[0], ozet.gunler[-1]),
                alt_baslik=HAFTALIK_ACIKLAMA, kaynak=KAYNAK, satirlar=tuple(ogeler))
