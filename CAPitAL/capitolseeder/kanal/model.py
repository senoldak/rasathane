"""Kanal kartlarının tek veri birimi: bir Kongre işlem beyanı."""
import datetime
import re
from dataclasses import dataclass
from typing import Optional

HISSE_TURLERI = {"", "ST", "Stock", "CS"}
ALIS = {"Purchase"}
SATIS = {"Sale (Full)", "Sale (Partial)"}


@dataclass(frozen=True)
class Beyan:
    id: str
    ilk_gorulme: str  # "YYYY-AA-GG" ya da "baslangic"
    uye: str
    parti: str  # D / R / I
    eyalet: str
    meclis: str  # Temsilciler / Senato
    ticker: str
    varlik: str
    varlik_turu: str
    islem: str  # kaynaktaki ham değer
    tutar_alt: int
    tutar_ust: int
    tutar_etiket: str
    islem_tarihi: datetime.date
    beyan_tarihi: datetime.date
    gecikme: int
    gec: bool
    belge: str

    @property
    def yon(self) -> Optional[str]:
        if self.islem in ALIS:
            return "Alış"
        if self.islem in SATIS:
            return "Satış"
        return None


# Kaynak bazı tahvil, mevduat sertifikası ve hazine bonolarını hisse kodu ve boş/CS türüyle veriyor.
_BORC_ADI = re.compile(r"\d[\d.,]*\s*%|\bCTF DEP\b|\bNOTE\b|\bBOND\b|\bDUE \d|\bMAT\b|\bT-?BILL\b", re.IGNORECASE)


def hisse_mi(b: Beyan) -> bool:
    return (
        bool(b.ticker)
        and "-" not in b.ticker
        and b.varlik_turu in HISSE_TURLERI
        and b.yon is not None
        and not _BORC_ADI.search(b.varlik)
    )


def kisa_ad(ad: str) -> str:
    parcalar = [p for p in ad.replace(",", " ").split() if p]
    if len(parcalar) < 2:
        return ad.strip()
    son = parcalar[-1]
    soyad = son
    if son.rstrip(".").lower() in {"jr", "sr", "ii", "iii", "iv"} and len(parcalar) >= 3:
        soyad = f"{parcalar[-2]} {son}"
    return f"{parcalar[0][0]}. {soyad}"


_SIRKET_EKLERI = re.compile(
    r"\b(common stock|class [a-z]|ordinary shares?|new|inc|incorporated|corp|corporation|"
    r"co|company|plc|ltd|limited|holdings?|hldgs|group|sa|nv|ag|adr|lp|llc)\b\.?",
    re.IGNORECASE,
)


def kisa_sirket(ad: str, uzunluk: int = 18) -> str:
    temiz = re.split(r"\s+-\s+", ad or "")[0]
    temiz = _SIRKET_EKLERI.sub("", temiz)
    temiz = re.sub(r"[\s,.&]+$", "", re.sub(r"\s+", " ", temiz)).strip(" ,.-")
    if not temiz:
        temiz = (ad or "").strip()
    if (ad or "").isupper() and len(temiz) > 4:  # kaynağın BÜYÜK HARF yazdığı adlar
        temiz = temiz.title()
    if len(temiz) > uzunluk:
        temiz = temiz[: uzunluk - 1].rstrip() + "…"
    return temiz


def _kisa_sayi(n: int) -> str:
    if n >= 1_000_000:
        return f"{round(n / 1_000_000)}M"
    return f"{round(n / 1000)}k"


def kisa_tutar(alt: int, ust: int) -> str:
    if not ust:
        return f"${_kisa_sayi(alt - 1)}+"
    return f"${_kisa_sayi(alt - 1)}–{_kisa_sayi(ust)}"
