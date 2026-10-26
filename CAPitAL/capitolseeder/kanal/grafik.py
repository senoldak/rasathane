"""CAPitAL Beyan Gecikmesi grafiği: işlem günü ile beyan günü arasında hissenin ve S&P 500'ün seyri."""
import bisect
import datetime
from typing import Optional

from capitolseeder.kanal.kart import FIKIR
from capitolseeder.kanal.model import Beyan, hisse_mi, kisa_ad, kisa_sirket, kisa_tutar
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Grafik, Hucre, Isaret

AD = "Beyan Gecikmesi"
GUN_SAYISI = 92
Seri = list[tuple[datetime.date, float]]


def gecikme_secimi(yeniler: list[Beyan]) -> Optional[Beyan]:
    """Günün en büyük tutarlı hisse alışı (aralığın üst sınırına göre); eşitlikte gecikmesi en uzun olan."""
    adaylar = [b for b in yeniler if hisse_mi(b) and b.yon == "Alış"]
    if not adaylar:
        return None
    return max(adaylar, key=lambda b: (max(b.tutar_ust, b.tutar_alt), b.gecikme))


def _sonraki(gunler: list[datetime.date], gun: datetime.date) -> datetime.date:
    i = bisect.bisect_left(gunler, gun)
    return gunler[min(i, len(gunler) - 1)]


def _onceki(gunler: list[datetime.date], gun: datetime.date) -> datetime.date:
    i = bisect.bisect_right(gunler, gun)
    return gunler[max(i - 1, 0)]


def _fiyat(x: float) -> str:
    return f"${x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _degisim(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}%{abs(x) * 100:.1f}".replace(".", ",")


def gecikme_grafigi(b: Beyan, bugun: datetime.date, kapanis: Seri, spy: Seri) -> Grafik:
    bas = min(bugun - datetime.timedelta(days=GUN_SAYISI), b.islem_tarihi - datetime.timedelta(days=7))
    seri = [(g, v) for g, v in kapanis if bas <= g <= bugun]
    gunler = [g for g, _ in seri]
    islem = _sonraki(gunler, b.islem_tarihi)
    beyan_g = _onceki(gunler, b.beyan_tarihi)
    deger = dict(seri)

    spy_gunleri = [g for g, _ in spy]
    spy_degeri = dict(spy)
    hizali = [spy_degeri[_onceki(spy_gunleri, g)] for g in gunler]
    olcek = seri[0][1] / hizali[0]

    uye = f"{kisa_ad(b.uye)} ({b.parti}-{b.eyalet})" if b.eyalet else kisa_ad(b.uye)
    kaynak = "Senate eFD" if b.meclis == "Senato" else "House Clerk"
    return Grafik(
        fikir=FIKIR, tarih=kagit.tarih_metni(bugun), baslik=f"{b.ticker} · {kisa_sirket(b.varlik, 28)}",
        alt_baslik=f"{uye} · {b.yon} {kisa_tutar(b.tutar_alt, b.tutar_ust)} · işlemden {b.gecikme} gün sonra beyan",
        ozet=(("İşlem günü", Hucre(_fiyat(deger[islem]))), ("Beyan günü", Hucre(_fiyat(deger[beyan_g]), vurgu=True)),
              ("Aradaki değişim", Hucre(_degisim(deger[beyan_g] / deger[islem] - 1)))),
        gunler=tuple(gunler), seri=tuple(v for _, v in seri), kaynak=f"{kaynak} · Yahoo Finance",
        karsilastirma=tuple(v * olcek for v in hizali), karsilastirma_adi="S&P 500",
        isaretler=(Isaret(islem, f"işlem {islem:%d.%m}"), Isaret(beyan_g, f"beyan {beyan_g:%d.%m}")),
        golge=(islem, beyan_g),
    )
