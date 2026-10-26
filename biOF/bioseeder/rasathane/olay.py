from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class OlayTuru(str, Enum):
    FAZ3_SONUC = "FAZ3_SONUC"
    FAZ2_SONUC = "FAZ2_SONUC"
    FDA_ONAY = "FDA_ONAY"
    FDA_RET = "FDA_RET"
    DURDURULDU = "DURDURULDU"
    TARIH_KAYDI = "TARIH_KAYDI"
    TAMAMLANDI = "TAMAMLANDI"
    SONUC_GIRILDI = "SONUC_GIRILDI"
    YENI_FAZ3 = "YENI_FAZ3"
    YENI_FAZ2 = "YENI_FAZ2"


ETIKET: Dict[OlayTuru, str] = {
    OlayTuru.FAZ3_SONUC: "FAZ 3 SONUÇ",
    OlayTuru.FAZ2_SONUC: "FAZ 2 SONUÇ",
    OlayTuru.FDA_ONAY: "FDA ONAY",
    OlayTuru.FDA_RET: "FDA RET",
    OlayTuru.DURDURULDU: "DURDURULDU",
    OlayTuru.TARIH_KAYDI: "TARİH KAYDI",
    OlayTuru.TAMAMLANDI: "TAMAMLANDI",
    OlayTuru.SONUC_GIRILDI: "SONUÇ GİRİLDİ",
    OlayTuru.YENI_FAZ3: "YENİ FAZ 3",
    OlayTuru.YENI_FAZ2: "YENİ FAZ 2",
}

GRI = "#94a3b8"
ZUMRUT = "#00f59b"
KIRMIZI = "#ff3366"
KEHRIBAR = "#ffb800"
CAMGOBEGI = "#00e5ff"

# Faz sonuçları bilerek nötr (gri): kart sonucun yönünü yorumlamaz.
RENK: Dict[OlayTuru, str] = {
    OlayTuru.FAZ3_SONUC: GRI,
    OlayTuru.FAZ2_SONUC: GRI,
    OlayTuru.FDA_ONAY: ZUMRUT,
    OlayTuru.FDA_RET: KIRMIZI,
    OlayTuru.DURDURULDU: KIRMIZI,
    OlayTuru.TARIH_KAYDI: KEHRIBAR,
    OlayTuru.TAMAMLANDI: CAMGOBEGI,
    OlayTuru.SONUC_GIRILDI: CAMGOBEGI,
    OlayTuru.YENI_FAZ3: CAMGOBEGI,
    OlayTuru.YENI_FAZ2: CAMGOBEGI,
}

ONCELIK: List[OlayTuru] = [
    OlayTuru.FDA_RET,
    OlayTuru.FDA_ONAY,
    OlayTuru.FAZ3_SONUC,
    OlayTuru.DURDURULDU,
    OlayTuru.FAZ2_SONUC,
    OlayTuru.TARIH_KAYDI,
    OlayTuru.TAMAMLANDI,
    OlayTuru.SONUC_GIRILDI,
    OlayTuru.YENI_FAZ3,
    OlayTuru.YENI_FAZ2,
]


@dataclass(frozen=True)
class Olay:
    kimlik: str
    tur: OlayTuru
    ticker: str
    satir: str
    ayrinti: str
    tarih: date
    faz3: bool = False
    mikro: bool = False
    baglanti: Optional[str] = None
    etiket_ek: Optional[str] = None

    @property
    def etiket(self) -> str:
        return self.etiket_ek or ETIKET[self.tur]


def buyuk_mu(o: Olay) -> bool:
    if o.tur in (OlayTuru.FAZ3_SONUC, OlayTuru.FDA_ONAY, OlayTuru.FDA_RET):
        return True
    return o.tur == OlayTuru.DURDURULDU and o.faz3


def sirala(olaylar: List[Olay]) -> List[Olay]:
    return sorted(olaylar, key=lambda o: (not buyuk_mu(o), ONCELIK.index(o.tur), o.ticker))
