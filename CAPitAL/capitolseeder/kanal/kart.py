"""CAPitAL kartları: veriyi Rasathane'nin ortak Kâğıt kartına çevirir."""
import datetime

from capitolseeder.kanal.model import Beyan, kisa_ad, kisa_sirket, kisa_tutar
from capitolseeder.kanal.performans import UyePerformansi
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Hucre, Kart, Satir
from capitolseeder.kanal.secim import HisseOzeti

FIKIR = "CAPitAL"
KAYNAK = "House Clerk / Senate eFD"
SAYFA_SATIRI = 6
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
         "Kasım", "Aralık"]
PERFORMANS_NOTU = (
    "Üyenin gerçek getirisi değildir; beyan edilen alımların işlem gününden bugüne fiyat değişimidir. "
    "Fark: aynı tarihlerde S&P 500'e göre puan."
)


def gunluk_alt_basligi(tarih: datetime.date, uye_sayisi: int, islem_sayisi: int, gosterilen: int) -> str:
    return f"En büyük {gosterilen} işlem · toplam {islem_sayisi} işlem, {uye_sayisi} üye"


def performans_alt_basligi(baslangic: datetime.date, bugun: datetime.date) -> str:
    if baslangic <= bugun - datetime.timedelta(days=365):
        return "Son 12 ayda beyan edilen alımlar · en az 5 alım"
    return f"{AYLAR[baslangic.month - 1]} {baslangic.year}'dan beri beyan edilen alımlar · en az 5 alım"


def yuzde(x: float) -> str:
    isaret = "+" if x >= 0 else "−"
    return f"{isaret}%{abs(x):.1f}".replace(".", ",")


def puan(x: float) -> str:
    isaret = "+" if x >= 0 else "−"
    return f"{isaret}{abs(x):.1f}".replace(".", ",")


def _uye(b: Beyan) -> str:
    return f"{kisa_ad(b.uye)} · {b.parti}-{b.eyalet}" if b.eyalet else kisa_ad(b.uye)


def _beyan_satiri(b: Beyan) -> Satir:
    sure = f"{b.gecikme} gün geç" if b.gec else f"{b.gecikme} günde"
    return Satir(ust=b.ticker, alt=f"{kisa_sirket(b.varlik, 28)} · {_uye(b)}",
                 sag=(Hucre(kisa_tutar(b.tutar_alt, b.tutar_ust), kalin=True,
                            alt=f"{b.yon or ''} · {sure}".strip(" ·"), alt_vurgu=b.gec),))


def gunluk_karti(secilen: list[Beyan], tarih: datetime.date, uye_sayisi: int, islem_sayisi: int) -> Kart:
    gosterilen = secilen[:SAYFA_SATIRI]
    kalan = islem_sayisi - len(gosterilen)
    return Kart(
        fikir=FIKIR, ad="Günün Kongre Beyanları", tarih=kagit.tarih_metni(tarih), kaynak=KAYNAK,
        alt_baslik=gunluk_alt_basligi(tarih, uye_sayisi, islem_sayisi, len(gosterilen)),
        satirlar=tuple(_beyan_satiri(b) for b in gosterilen),
        not_=f"+{kalan} işlem daha aynı gün beyan edildi." if kalan > 0 else "",
    )


def _partiler(o: HisseOzeti) -> str:
    return ", ".join(f"{p} {o.partiler[p]}" for p in ("D", "R", "I") if o.partiler.get(p))


def haftalik_karti(ozet: list[HisseOzeti], pazartesi: datetime.date) -> Kart:
    satirlar = tuple(
        Satir(ust=o.ticker, etiket="iki parti" if o.iki_parti_alim else "",
              alt=" · ".join(p for p in (kisa_sirket(o.varlik, 28), _partiler(o)) if p),
              sag=(Hucre(kisa_tutar(o.tutar_alt, o.tutar_ust), kalin=True,
                         alt=f"{len(o.alan_uyeler)} alan · {len(o.satan_uyeler)} satan"),))
        for o in ozet[:SAYFA_SATIRI])
    return Kart(fikir=FIKIR, ad="Haftanın Özeti",
                tarih=kagit.aralik_metni(pazartesi, pazartesi + datetime.timedelta(days=4)),
                alt_baslik="En çok üyenin işlem yaptığı hisseler (üye sayısı)", kaynak=KAYNAK, satirlar=satirlar)


def performans_karti(
    uyeler: list[UyePerformansi], en_yuksek: bool, baslangic: datetime.date, bugun: datetime.date
) -> Kart:
    satirlar = tuple(
        Satir(ust=kisa_ad(p.uye), alt=f"{p.parti}-{p.eyalet} · {p.alim_sayisi} alım",
              sag=(Hucre(yuzde(p.ort_degisim)), Hucre(puan(p.fark), kalin=True, vurgu=True)))
        for p in uyeler[:5])
    return Kart(
        fikir=FIKIR, ad="Beyan Performansı: " + ("En Yüksek" if en_yuksek else "En Düşük"),
        tarih=kagit.tarih_metni(bugun), alt_baslik=performans_alt_basligi(baslangic, bugun),
        kaynak=KAYNAK, satirlar=satirlar, sutunlar=("Üye", "Hisseler", "Fark"), not_=PERFORMANS_NOTU,
    )
