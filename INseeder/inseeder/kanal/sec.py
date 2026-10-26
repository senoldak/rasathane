"""SEC EDGAR günlük Form 4 dizini ve beyanların indirilmesi (SEC Fair Access'e uygun)."""
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, List, Optional, Tuple

import httpx

from inseeder.collectors.sec_edgar import extract_form4_xml, parse_form4_beyan
from inseeder.kanal.model import Beyan, beyanlar_olustur
from inseeder.kanal.takvim import federal_tatil_mi

logger = logging.getLogger("inseeder.kanal.sec")

ARCHIVES = "https://www.sec.gov/Archives"
EN_AZ_BEYAN = 100
EN_COK_HATA_ORANI = 0.10
BEKLE_404_SN = 1200
BEKLE_404_DENEME = 9
HATA_BEKLEMELERI = (5, 15)
_ACC_RE = re.compile(r"edgar/data/(\d+)/(\d{10}-\d{2}-\d{6})\.txt$")


class KanalHatasi(Exception):
    """Gönderimi durduran, sahibe bildirilecek hata."""


@dataclass
class GunSonucu:
    gun: date
    dizin_var: bool
    toplam: int = 0
    okunan: int = 0
    hatali: int = 0
    beyanlar: List[Beyan] = field(default_factory=list)


def dizin_url(gun: date) -> str:
    ceyrek = (gun.month - 1) // 3 + 1
    return f"{ARCHIVES}/edgar/daily-index/{gun.year}/QTR{ceyrek}/form.{gun:%Y%m%d}.idx"


def dizin_ayristir(metin: str) -> List[Tuple[str, str, str]]:
    """Dizindeki tekil Form 4 satırları: (cik, accession_no, dosya_yolu). 4/A alınmaz."""
    sonuc: List[Tuple[str, str, str]] = []
    gorulen = set()
    for satir in metin.splitlines():
        if not satir.startswith("4 "):
            continue
        m = _ACC_RE.search(satir.strip())
        if not m or m.group(2) in gorulen:
            continue
        gorulen.add(m.group(2))
        sonuc.append((m.group(1), m.group(2), m.group(0)))
    return sonuc


class SecIstemcisi:
    def __init__(self, client: httpx.Client, uyku: Callable[[float], None] = time.sleep,
                 saniyede: float = 8.0):
        self.client = client
        self.uyku = uyku
        self.aralik = 1.0 / saniyede

    def _getir(self, url: str) -> Optional[httpx.Response]:
        """GET; 5xx/429/ağ hatasında 3 deneme. 404 ya da başarı yanıtı döner, aksi None."""
        for deneme in range(len(HATA_BEKLEMELERI) + 1):
            try:
                yanit = self.client.get(url)
                if yanit.status_code == 200 or yanit.status_code == 404:
                    return yanit
                if yanit.status_code == 403:
                    raise KanalHatasi(
                        "SEC isteği reddetti (403). SEC_USER_AGENT gerçek, ulaşılabilir bir e-posta "
                        "içermeli (ör. 'INseeder Ad Soyad eposta@ornek.com'); "
                        f"GitHub noreply adresleri reddediliyor. Adres: {url}"
                    )
                logger.warning(f"SEC {yanit.status_code}: {url}")
            except httpx.HTTPError as e:
                logger.warning(f"SEC ağ hatası {url}: {e}")
            if deneme < len(HATA_BEKLEMELERI):
                self.uyku(HATA_BEKLEMELERI[deneme])
        return None

    def _dizin(self, gun: date, bekle_404: bool) -> Optional[str]:
        url = dizin_url(gun)
        for deneme in range(BEKLE_404_DENEME + 1):
            yanit = self._getir(url)
            if yanit is None:
                raise KanalHatasi(f"SEC günlük dizini alınamadı: {url}")
            if yanit.status_code == 200:
                return yanit.text
            if federal_tatil_mi(gun):
                return None
            if not bekle_404:
                # Doldurma: plansız SEC kapanışı (yas günü vb.) sonraki günleri tıkamasın.
                logger.warning(f"{gun:%d.%m.%Y} için SEC dizini yok; gün boş sayıldı: {url}")
                return None
            if deneme == BEKLE_404_DENEME:
                break
            logger.info(f"Dizin henüz yok, {BEKLE_404_SN} sn sonra yeniden denenecek: {url}")
            self.uyku(BEKLE_404_SN)
        raise KanalHatasi(f"{gun:%d.%m.%Y} iş günü ama SEC günlük dizini yayımlanmamış: {url}")

    def gun_isle(self, gun: date, bekle_404: bool = True) -> GunSonucu:
        metin = self._dizin(gun, bekle_404)
        if metin is None:
            return GunSonucu(gun=gun, dizin_var=False)

        satirlar = dizin_ayristir(metin)
        sonuc = GunSonucu(gun=gun, dizin_var=True, toplam=len(satirlar))
        if sonuc.toplam < EN_AZ_BEYAN:
            raise KanalHatasi(
                f"{gun:%d.%m.%Y} dizininde yalnız {sonuc.toplam} Form 4 var (en az {EN_AZ_BEYAN} beklenir)."
            )

        for sira, (cik, acc, yol) in enumerate(satirlar, 1):
            if sira % 250 == 0:
                logger.info(f"{gun:%d.%m.%Y}: {sira}/{sonuc.toplam} beyan indirildi")
            self.uyku(self.aralik)
            yanit = self._getir(f"{ARCHIVES}/{yol}")
            xml = extract_form4_xml(yanit.text) if yanit is not None and yanit.status_code == 200 else None
            ayristirma = parse_form4_beyan(xml) if xml else None
            if ayristirma is None:
                sonuc.hatali += 1
                continue
            sonuc.okunan += 1
            sec_url = f"{ARCHIVES}/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.htm"
            sonuc.beyanlar.extend(beyanlar_olustur(ayristirma, acc, gun, sec_url))

        if sonuc.hatali / sonuc.toplam > EN_COK_HATA_ORANI:
            raise KanalHatasi(
                f"{gun:%d.%m.%Y}: {sonuc.toplam} beyanın {sonuc.hatali} tanesi okunamadı (%10 sınırı aşıldı)."
            )
        return sonuc
