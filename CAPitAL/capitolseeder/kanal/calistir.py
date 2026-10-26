"""Kanal akışı: kaynak → doğrulama → arşiv → kartlar → Telegram. `python -m capitolseeder.kanal`."""
import argparse
import datetime
import logging
import os
from dataclasses import replace
from pathlib import Path
from typing import Callable, Mapping, Optional

from capitolseeder.kanal.arsiv import (
    beyanlari_oku,
    beyanlari_yaz,
    gonderildi_mi,
    gonderim_ekle,
    yenileri_ayir,
)
from capitolseeder.kanal.kaynak import VeriHatasi, dogrula, indir, kongre_beyanlari
from capitolseeder.kanal.grafik import AD as GRAFIK_AD, GUN_SAYISI, gecikme_grafigi, gecikme_secimi
from capitolseeder.kanal.kart import FIKIR, gunluk_karti, haftalik_karti, performans_karti
from capitolseeder.kanal.model import Beyan, hisse_mi
from rasathane_ortak import kagit
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi
from capitolseeder.kanal.performans import (
    Fiyatlar,
    fiyatlari_cek,
    pencere_baslangici,
    FiyatHatasi,
    performans,
)
from capitolseeder.kanal.secim import ayin_ilk_cumasi, gunluk, haftalik
from capitolseeder.kanal.telegram import GonderimHatasi, gonder, sahibe_bildir

logger = logging.getLogger("capitolseeder.kanal")

def _en_son_beyanlar(beyanlar: list[Beyan]) -> tuple[Optional[datetime.date], list[Beyan]]:
    hisseler = [b for b in beyanlar if hisse_mi(b)]
    if not hisseler:
        return None, []
    en_son = max(b.beyan_tarihi for b in hisseler)
    return en_son, [b for b in hisseler if b.beyan_tarihi == en_son]


def _gunluk_havuzu(
    yeniler: list[Beyan], kaynak: list[Beyan], bugun: datetime.date, hepsi: bool
) -> tuple[datetime.date, list[Beyan]]:
    tarih, havuz = bugun, [b for b in yeniler if hisse_mi(b)]
    if not havuz and hepsi:  # önizleme: kaynaktaki en son beyan günü
        en_son, havuz = _en_son_beyanlar(kaynak)
        tarih = en_son or bugun
    return tarih, havuz


def _gunluk(yeniler: list[Beyan], kaynak: list[Beyan], bugun: datetime.date, hepsi: bool) -> Optional[kagit.Kart]:
    tarih, havuz = _gunluk_havuzu(yeniler, kaynak, bugun, hepsi)
    secilen = gunluk(havuz)
    if not secilen:
        return None
    return gunluk_karti(secilen, tarih, len({b.uye for b in havuz}), len(havuz))


def _haftalik(arsiv: list[Beyan], kaynak: list[Beyan], bugun: datetime.date, hepsi: bool) -> Optional[kagit.Kart]:
    pazartesi = bugun - datetime.timedelta(days=bugun.weekday())
    ozet = haftalik(arsiv, pazartesi)
    if not ozet and hepsi:  # önizleme: son 7 günün beyan tarihine göre
        en_son, _ = _en_son_beyanlar(kaynak)
        if en_son:
            ozet = haftalik(kaynak, en_son - datetime.timedelta(days=6), gun_sayisi=7, alan="beyan_tarihi")
            pazartesi = en_son - datetime.timedelta(days=en_son.weekday())
    return haftalik_karti(ozet, pazartesi) if ozet else None


def _performans(
    arsiv: list[Beyan], bugun: datetime.date, fiyat_cekici: Callable[..., Fiyatlar]
) -> list[tuple[str, kagit.Kart]]:
    baslangic = pencere_baslangici(arsiv, bugun)
    alimlar = [b for b in arsiv if b.yon == "Alış" and hisse_mi(b) and b.beyan_tarihi >= baslangic]
    semboller = sorted({b.ticker for b in alimlar})
    en_eski = min((b.islem_tarihi for b in alimlar), default=baslangic)
    try:
        ust, alt, bas = performans(arsiv, fiyat_cekici(semboller, en_eski), bugun)
    except FiyatHatasi as e:  # Yahoo kısıtlaması: bir kez daha dene
        logger.warning("Fiyatlar eksik, yeniden deneniyor: %s", e)
        ust, alt, bas = performans(arsiv, fiyat_cekici(semboller, en_eski), bugun)
    kartlar = [("performans", performans_karti(ust, True, bas, bugun))]
    if alt:
        kartlar.append(("performans_dusuk", performans_karti(alt, False, bas, bugun)))
    return kartlar


def _grafik(havuz: list[Beyan], tarih: datetime.date, fiyat_cekici: Callable[..., Fiyatlar]) -> Optional[bytes]:
    b = gecikme_secimi(havuz)
    if b is None:
        return None
    bas = min(tarih - datetime.timedelta(days=GUN_SAYISI), b.islem_tarihi - datetime.timedelta(days=7))
    fiyatlar = fiyat_cekici([b.ticker], bas)
    if not fiyatlar.get(b.ticker) or not fiyatlar.get("SPY"):
        raise FiyatHatasi(f"{b.ticker} ya da SPY fiyatı yok")
    return kagit.grafik_ciz(gecikme_grafigi(b, tarih, fiyatlar[b.ticker], fiyatlar["SPY"]))


def calistir(
    bugun: datetime.date,
    kuru: bool,
    veri_dizini: Path,
    cikti_dizini: Path,
    satirlar: Optional[list[dict]] = None,
    ortam: Mapping[str, str] = os.environ,
    fiyat_cekici: Callable[..., Fiyatlar] = fiyatlari_cek,
    gonderici: Callable[..., list[int]] = gonder,
    bildirici: Callable[[str, str, str], None] = sahibe_bildir,
    hepsi: bool = False,
    grafik_fiyat_cekici: Optional[Callable[..., Fiyatlar]] = None,
) -> list[str]:
    token = ortam.get("TELEGRAM_BOT_TOKEN", "")
    kuru = kuru or ortam.get("KANAL_GONDER") != "1"
    hepsi = hepsi and kuru

    def bildir(metin: str) -> None:
        logger.error(metin)
        bildirici(token, ortam.get("TELEGRAM_SAHIP_ID", ""), f"CAPitAL kanalı ({bugun}): {metin}")

    beyan_dosyasi = veri_dizini / "beyanlar.csv"
    gonderim_dosyasi = veri_dizini / "gonderimler.csv"
    if not kuru and gonderildi_mi(gonderim_dosyasi, bugun):
        logger.info("%s zaten gönderilmiş; çıkılıyor.", bugun)
        return []

    try:
        if satirlar is None:
            satirlar = indir()
        dogrula(satirlar, bugun)
    except VeriHatasi as e:
        bildir(f"Veri hatası, bugün gönderim yok. {e}")
        raise

    arsiv = beyanlari_oku(beyan_dosyasi)
    kaynak = kongre_beyanlari(satirlar, bugun.isoformat())
    ilk_kosu = not arsiv
    if ilk_kosu:
        logger.info("Arşiv boş: ilk koşu, %d beyan başlangıç olarak kaydediliyor.", len(kaynak))
        yeniler: list[Beyan] = []
        yeni_arsiv = [replace(b, ilk_gorulme="baslangic") for b in kaynak]
    else:
        yeni = yenileri_ayir(kaynak, arsiv)
        yeni_arsiv = arsiv + yeni
        # Gönderimi yarıda kalan günün yeniden koşusu: bugün arşive giren beyanlar da günün havuzundadır;
        # giden kartlar gonderilen_kartlar.csv sayesinde atlanır, kalanlar (ör. grafik) yeniden üretilir.
        yeniler = [b for b in arsiv if b.ilk_gorulme == bugun.isoformat()] + yeni
    logger.info("Yeni Kongre beyanı: %d (hisse: %d)", len(yeniler), sum(1 for b in yeniler if hisse_mi(b)))

    kartlar: list[tuple[str, kagit.Kart]] = []
    gunluk_kart = _gunluk(yeniler, kaynak, bugun, hepsi)
    grafik_png = None
    if gunluk_kart:
        kartlar.append(("gunluk", gunluk_kart))
        if grafik_fiyat_cekici:
            try:
                grafik_tarihi, havuz = _gunluk_havuzu(yeniler, kaynak, bugun, hepsi)
                grafik_png = _grafik(havuz, grafik_tarihi, grafik_fiyat_cekici)
            except Exception as e:  # grafik yalnız ektir; diğer kartlar yine gider
                bildir(f"Beyan Gecikmesi grafiği üretilemedi: {e}")
    if bugun.weekday() == 4 or hepsi:
        haftalik_kart = _haftalik(yeni_arsiv, kaynak, bugun, hepsi)
        if haftalik_kart:
            kartlar.append(("haftalik", haftalik_kart))
    if (ayin_ilk_cumasi(bugun) and not ilk_kosu) or hepsi:
        try:
            kartlar.extend(_performans(yeni_arsiv, bugun, fiyat_cekici))
        except Exception as e:  # fiyat kaynağı: diğer kartlar yine gider
            bildir(f"Beyan Performansı kartı üretilemedi: {e}")

    cikti_dizini.mkdir(parents=True, exist_ok=True)
    gidenler: list[Giden] = []
    adlar: list[str] = []
    for ad, kart in kartlar:
        for sf in kagit.ciz(kart):
            dosya = f"{bugun.isoformat()}_{ad}.png" if sf.no == 1 else f"{bugun.isoformat()}_{ad}_{sf.no}.png"
            (cikti_dizini / dosya).write_bytes(sf.png)
            gidenler.append(Giden(ad, sf.no, sf.png, kagit.mesaj_metni(FIKIR, kart.ad, kart.tarih, sf.no, sf.toplam)))
        adlar.append(ad)
        if ad == "gunluk" and grafik_png:
            (cikti_dizini / f"{bugun.isoformat()}_grafik.png").write_bytes(grafik_png)
            gidenler.append(Giden("grafik", 1, grafik_png, kagit.mesaj_metni(FIKIR, GRAFIK_AD, kart.tarih)))
            adlar.append("grafik")
    logger.info("Kartlar: %s", adlar or "yok")

    if kuru:
        # Kuru koşu arşivi yalnız soğuk başlangıçta doldurur; önizleme o günün yeni beyanlarını "yemez".
        if ilk_kosu:
            beyanlari_yaz(beyan_dosyasi, yeni_arsiv)
        return adlar
    if not kartlar or ilk_kosu:
        beyanlari_yaz(beyan_dosyasi, yeni_arsiv)
        return []

    kayit = GonderimKaydi(veri_dizini / "gonderilen_kartlar.csv")
    gun = bugun.isoformat()
    try:
        hedef = ortam.get("TELEGRAM_HEDEF", "")
        if not token or not hedef:
            raise GonderimHatasi("TELEGRAM_BOT_TOKEN ya da TELEGRAM_HEDEF tanımlı değil.")
        kimlikler = gonderici(token, hedef, gun, gidenler, kayit)
    except GonderimHatasi as e:
        # En az bir kart gittiyse arşiv yazılır; yoksa yeni beyanlar ertesi gün yeniden "yeni" sayılırdı.
        if any(kayit.gonderildi_mi(gun, g.kart, g.sayfa) for g in gidenler):
            beyanlari_yaz(beyan_dosyasi, yeni_arsiv)
            bildir(f"Gönderim yarıda kaldı; giden kartlar kaydedildi, yeniden çalıştırınca kalanlar gider. {e}")
        else:
            bildir(f"Gönderim başarısız, arşiv güncellenmedi. {e}")
        raise
    beyanlari_yaz(beyan_dosyasi, yeni_arsiv)
    gonderim_ekle(gonderim_dosyasi, bugun, adlar, kimlikler[0] if kimlikler else 0)
    return adlar


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m capitolseeder.kanal", description="CAPitAL → Rasathane kartları")
    ap.add_argument("--kuru", action="store_true", help="Kartları üret, gönderme")
    ap.add_argument("--hepsi", action="store_true", help="Kuru koşuda üç kartın önizlemesini üret")
    ap.add_argument("--tarih", type=datetime.date.fromisoformat, help="YYYY-AA-GG (varsayılan: UTC'ye göre bugün)")
    ap.add_argument("--kaynak", type=Path, help="Yerel JSON kaynak dosyası")
    ap.add_argument("--veri", type=Path, default=Path("kanal/veri"))
    ap.add_argument("--cikti", type=Path, default=Path("kanal/cikti"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    logging.getLogger("httpx").setLevel(logging.WARNING)  # istek satırları bot anahtarını içerir
    # Koşu UTC 20:30'da (İstanbul 23:30) başlar; GitHub gecikirse İstanbul'da gün dönebilir,
    # bu yüzden gün UTC'ye göre alınır (iki saat dilimi o saatte aynı günü gösterir).
    bugun = a.tarih or datetime.datetime.now(datetime.timezone.utc).date()
    satirlar = None
    if a.kaynak:
        import json

        satirlar = json.loads(a.kaynak.read_text(encoding="utf-8"))
    try:
        calistir(bugun, a.kuru, a.veri, a.cikti, satirlar=satirlar, hepsi=a.hepsi,
                 grafik_fiyat_cekici=fiyatlari_cek)
    except (VeriHatasi, GonderimHatasi) as e:  # sahibine calistir içinde bildirildi
        logger.error("Kanal koşusu başarısız: %s", e)
        return 1
    except Exception as e:
        logger.exception("Kanal koşusunda beklenmeyen hata")
        sahibe_bildir(
            os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            os.environ.get("TELEGRAM_SAHIP_ID", ""),
            f"CAPitAL kanalı ({bugun}): beklenmeyen hata, bugün gönderim yok. {type(e).__name__}: {e}",
        )
        return 1
    return 0
