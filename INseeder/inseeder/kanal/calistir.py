"""Rasathane INseeder konusu: günlük akış (python -m inseeder.kanal)."""
import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import httpx

from inseeder.kanal.grafik import AD as GRAFIK_AD, GUN_SAYISI, FiyatCekici, grafik_karti, grafik_secimi, yahoo_kapanislar
from inseeder.kanal.kartlar import FIKIR, gunluk_kart, haftalik_kart
from inseeder.kanal.kayit import Kayit
from rasathane_ortak import kagit
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi, sirayla_gonder
from inseeder.kanal.sec import KanalHatasi, SecIstemcisi
from inseeder.kanal.secim import gunluk_alimlar, haftalik_ozet, kanala_uygun
from inseeder.kanal.takvim import anlatilan_gun, hafta_gunleri, istanbul_bugun, onceki_is_gunleri
from inseeder.kanal.telegram import TelegramIstemcisi

logger = logging.getLogger("inseeder.kanal")


@dataclass
class Ayarlar:
    kuru: bool
    tarih: Optional[date]
    doldur: int
    cikti: Path
    veri: Path
    bugun: date
    hedef: Optional[str]
    token: Optional[str]
    sahip_id: Optional[str]


def _isle(sec: SecIstemcisi, kayit: Kayit, gun: date, bekle_404: bool) -> None:
    sonuc = sec.gun_isle(gun, bekle_404=bekle_404)
    kayit.ekle([b for b in sonuc.beyanlar if kanala_uygun(b)])
    kayit.islendi(gun)


def _gidenler(anahtar: str, kart: kagit.Kart) -> List[Giden]:
    return [Giden(anahtar, sf.no, sf.png, kagit.mesaj_metni(FIKIR, kart.ad, kart.tarih, sf.no, sf.toplam))
            for sf in kagit.ciz(kart)]


def _yaz(cikti: Path, ad: str, gidenler: List[Giden]) -> None:
    for g in gidenler:
        (cikti / (f"{ad}.png" if g.sayfa == 1 else f"{ad}_{g.sayfa}.png")).write_bytes(g.png)


def _grafik_gideni(gun: date, satirlar: list, fiyat_cekici: FiyatCekici) -> Optional[Giden]:
    onbellek: dict = {}

    def seri(sembol: str):
        if sembol not in onbellek:
            onbellek[sembol] = fiyat_cekici(sembol, gun - timedelta(days=GUN_SAYISI + 10), gun + timedelta(days=1))
        return onbellek[sembol]

    def kapanis(sembol: str) -> Optional[float]:
        once = [v for g, v in seri(sembol) if g <= gun]
        return once[-1] if once else None

    sembol = grafik_secimi(satirlar, kapanis)
    if sembol is None:
        logger.info("Fiyat grafiği için uygun alım yok.")
        return None
    tarih = kagit.tarih_metni(gun)
    png = kagit.grafik_ciz(grafik_karti(gun, sembol, satirlar, seri(sembol)))
    return Giden("grafik", 1, png, kagit.mesaj_metni(FIKIR, GRAFIK_AD, tarih))


def calistir(ay: Ayarlar, sec: SecIstemcisi, tg: Optional[TelegramIstemcisi],
             fiyat_cekici: Optional[FiyatCekici] = None) -> str:
    gun = ay.tarih or anlatilan_gun(ay.bugun)
    kayit = Kayit(ay.veri)

    islenen = kayit.islenen_gunler()
    for g in onceki_is_gunleri(gun, ay.doldur) if ay.doldur > 0 else []:
        if g not in islenen:
            logger.info(f"Eksik gün kayda geçiriliyor: {g}")
            _isle(sec, kayit, g, bekle_404=False)
    if not ay.kuru:
        kayit.kaydet()  # anlatılan gün başarısız olsa da doldurma emeği kaybolmasın
    _isle(sec, kayit, gun, bekle_404=True)

    beyanlar = kayit.beyanlar()
    satirlar = gunluk_alimlar(beyanlar, gun)
    ozet = haftalik_ozet(beyanlar, gun) if gun.weekday() == 4 else None
    if ozet is not None and not ozet.kumeler and not ozet.satislar:
        ozet = None
    pazartesi = hafta_gunleri(gun)[0]

    ay.cikti.mkdir(parents=True, exist_ok=True)
    gonder_gunluk = bool(satirlar) and not kayit.gunluk_gonderildi_mi(gun)
    gonder_haftalik = bool(ozet) and not kayit.haftalik_gonderildi_mi(pazartesi)
    gidenler: List[Giden] = []
    aciklamalar: List[str] = []
    if satirlar:
        gunluk = _gidenler("gunluk", gunluk_kart(gun, satirlar))
        _yaz(ay.cikti, f"gunluk_{gun}", gunluk)
        aciklamalar += [g.aciklama for g in gunluk]
        if gonder_gunluk:
            gidenler += gunluk
        grafik = None
        if fiyat_cekici:
            try:
                grafik = _grafik_gideni(gun, satirlar, fiyat_cekici)
            except Exception as e:  # grafik yalnız ektir; günlük akışı durdurmaz
                logger.warning(f"Fiyat grafiği çizilemedi: {e}")
                if tg and ay.sahip_id and not ay.kuru and ay.hedef:
                    tg.sahibe_yaz(ay.sahip_id, f"INseeder fiyat grafiği ({gun:%d.%m.%Y}) atlandı: {e}")
        if grafik:
            _yaz(ay.cikti, f"grafik_{gun}", [grafik])
            aciklamalar.append(grafik.aciklama)
            if gonder_gunluk:
                gidenler.append(grafik)
    if ozet:
        haftalik = _gidenler("haftalik", haftalik_kart(ozet))
        _yaz(ay.cikti, f"haftalik_{gun}", haftalik)
        aciklamalar += [g.aciklama for g in haftalik]
        if gonder_haftalik:
            gidenler += haftalik
    if aciklamalar:
        (ay.cikti / f"aciklama_{gun}.txt").write_text("\n".join(aciklamalar) + "\n", encoding="utf-8")

    if not satirlar and not ozet:
        sonuc = "bos"
    elif ay.hedef and not ay.kuru and not (ay.token and tg):
        raise KanalHatasi("TELEGRAM_HEDEF tanımlı ama TELEGRAM_BOT_TOKEN yok; gönderim yapılamadı.")
    elif ay.kuru or not ay.hedef:
        sonuc = "kuru"
    elif not gidenler:
        sonuc = "zaten_gonderildi"
    else:
        sirayla_gonder(tg.istek, tg.token, ay.hedef, gun.isoformat(), gidenler,
                       GonderimKaydi(ay.veri / "gonderilen_kartlar.csv"), uyku=tg.uyku)
        if gonder_gunluk:
            kayit.gunluk_gonderildi(gun)
        if gonder_haftalik:
            kayit.haftalik_gonderildi(pazartesi)
        sonuc = "gonderildi"

    kayit.buda(ay.bugun)
    if not ay.kuru:
        kayit.kaydet()
    logger.info(f"{gun}: {sonuc} ({len(satirlar)} alım, haftalık: {'var' if ozet else 'yok'})")
    return sonuc


def _argumanlar(argv: Optional[List[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m inseeder.kanal",
                                description="Rasathane INseeder konusu için günlük kartlar")
    p.add_argument("--kuru", action="store_true", help="kartları üret, gönderme, kayıtlara dokunma")
    p.add_argument("--tarih", type=date.fromisoformat, help="anlatılacak dosyalama günü (YYYY-AA-GG)")
    p.add_argument("--doldur", type=int, default=7, help="geriye doğru kayda geçirilecek iş günü (0: kapalı)")
    p.add_argument("--cikti", type=Path, default=Path("kanal_cikti"))
    p.add_argument("--veri", type=Path, default=Path("kanal_veri"))
    p.add_argument("--bugun", type=date.fromisoformat, help="İstanbul tarihi yerine bu gün (deneme için)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None, sec_istemcisi: Optional[SecIstemcisi] = None,
         http_istemcisi: Optional[httpx.Client] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # httpx her isteği INFO'da loglar: SEC'te binlerce satır, Telegram URL'sinde bot anahtarı.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    arg = _argumanlar(argv)
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    if not ua:
        print("SEC_USER_AGENT tanımlı değil. SEC, iletişim e-postası içeren bir User-Agent ister "
              "(ör. 'INseeder Ad Soyad eposta@ornek.com').", file=sys.stderr)
        return 2
    token = os.getenv("TELEGRAM_BOT_TOKEN") or None
    ay = Ayarlar(
        kuru=arg.kuru, tarih=arg.tarih, doldur=arg.doldur, cikti=arg.cikti, veri=arg.veri,
        bugun=arg.bugun or istanbul_bugun(), hedef=os.getenv("TELEGRAM_HEDEF") or None,
        token=token, sahip_id=os.getenv("TELEGRAM_SAHIP_ID") or None,
    )
    sec = sec_istemcisi or SecIstemcisi(httpx.Client(headers={"User-Agent": ua}, timeout=30.0,
                                                     follow_redirects=True))
    tg = TelegramIstemcisi(http_istemcisi or httpx.Client(timeout=60.0), token) if token else None
    try:
        calistir(ay, sec, tg, fiyat_cekici=yahoo_kapanislar)
        return 0
    except Exception as e:
        gun = ay.tarih or anlatilan_gun(ay.bugun)
        logger.exception("Kanal koşusu başarısız")
        if tg and ay.sahip_id:
            tg.sahibe_yaz(ay.sahip_id, f"INseeder kanal hatası ({gun:%d.%m.%Y}): {e}\n"
                                       "Gönderilmeyen kartlar yeniden çalıştırınca gider.")
        return 1
