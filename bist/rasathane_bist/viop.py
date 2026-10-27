"""Borsa İstanbul VİOP (vadeli işlem ve opsiyon) günlük bülteni okuyucusu ve opsiyon kodu çözücü."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date

_URL = "https://borsaistanbul.com/viopdata/viop_{}.csv"


def viop_bulteni_url(gun: date) -> str:
    return _URL.format(gun.strftime("%Y%m%d"))


@dataclass(frozen=True)
class ViopSatiri:
    kod: str
    ad: str
    pazar: str
    segment: str
    tip: str
    sinif: str
    dayanak: str
    vade: date
    uzlasma: float
    onceki_uzlasma: float
    uzlasma_degisim_yuzde: float
    kapanis: float
    hacim_tl: float
    prim_hacmi: float
    lot: int
    islem_sayisi: int
    acik_pozisyon: int
    acik_pozisyon_degisimi: int


def _sayi(metin: str) -> float:
    metin = metin.strip()
    return float(metin) if metin else 0.0


def viop_bulteni_oku(csv_bayt: bytes) -> tuple[date, list[ViopSatiri]]:
    """CSV baytlarını okur: `;` ayraç, ilk iki satır (TR/EN) başlık, sütunlar başlık adıyla.

    Dosya düz ASCII; latin-1 çözmek her bayt için güvenlidir. Boş sayı 0 olur.
    """
    okuyucu = csv.reader(io.StringIO(csv_bayt.decode("latin-1")), delimiter=";")
    basliklar = next(okuyucu)
    next(okuyucu)  # İngilizce başlık satırı
    # " AGIRLIKLI ORTALAMA FIYAT" gibi başında boşluk olan başlıklara karşı kırpılır.
    sutun = {ad.strip(): i for i, ad in enumerate(basliklar)}

    def ara(ad: str) -> int:
        if ad not in sutun:
            raise ValueError(f"bültende sütun yok: {ad}")
        return sutun[ad]

    i_tarih = ara("TARIH")
    i_kod = ara("SOZLESME KODU")
    i_ad = ara("SOZLESME ADI")
    i_pazar = ara("PAZAR")
    i_seg = ara("PAZAR SEGMENTI")
    i_tip = ara("SOZLESME TIPI")
    i_sinif = ara("SOZLESME SINIFI")
    i_dayanak = ara("DAYANAK VARLIK")
    i_vade = ara("VADE TARIHI")
    i_uzl = ara("UZLASMA FIYATI")
    i_onc = ara("ONCEKI UZLASMA FIYATI")
    i_deg = ara("UZLASMA FIYATI DEGISIMI (%)")
    i_kap = ara("KAPANIS FIYATI")
    i_hacim = ara("ISLEM HACMI")
    i_prim = ara("PRIM HACMI")
    i_lot = ara("ISLEM MIKTARI")
    i_islem = ara("ISLEM SAYISI")
    i_acik = ara("ACIK POZISYON")
    i_acik_deg = ara("ACIK POZISYON DEGISIMI")

    gunler: set[date] = set()
    satirlar: list[ViopSatiri] = []
    for s in okuyucu:
        if not s or not any(s):
            continue
        gunler.add(date.fromisoformat(s[i_tarih].strip()))
        satirlar.append(
            ViopSatiri(
                kod=s[i_kod].strip(),
                ad=s[i_ad].strip(),
                pazar=s[i_pazar].strip(),
                segment=s[i_seg].strip(),
                tip=s[i_tip].strip(),
                sinif=s[i_sinif].strip(),
                dayanak=s[i_dayanak].strip(),
                vade=date.fromisoformat(s[i_vade].strip()),
                uzlasma=_sayi(s[i_uzl]),
                onceki_uzlasma=_sayi(s[i_onc]),
                uzlasma_degisim_yuzde=_sayi(s[i_deg]),
                kapanis=_sayi(s[i_kap]),
                hacim_tl=_sayi(s[i_hacim]),
                prim_hacmi=_sayi(s[i_prim]),
                lot=int(_sayi(s[i_lot])),
                islem_sayisi=int(_sayi(s[i_islem])),
                acik_pozisyon=int(_sayi(s[i_acik])),
                acik_pozisyon_degisimi=int(_sayi(s[i_acik_deg])),
            )
        )
    if len(gunler) != 1:
        raise ValueError(f"bültende tek tarih beklenirdi, bulunan: {sorted(gunler)}")
    return next(iter(gunler)), satirlar


@dataclass(frozen=True)
class OpsiyonSarti:
    dayanak: str
    tur: str  # "C" alım / "P" satım
    kullanim: float
    stil: str  # "E" Avrupa / "A" Amerikan


# O_ + dayanak + stil + vade (AAYY; esnek opsiyonlarda GGAAYY) + C/P + kullanım fiyatı.
# Fiziki teslimli döviz opsiyonlarında `O_P_`, esnek opsiyonlarda `TM_` öneki vardır.
_OPSIYON = re.compile(
    r"^(?:TM_)?O_(?:P_)?(?P<dayanak>[A-Z0-9]+?)(?P<stil>[EA])(?P<vade>\d{4}|\d{6})"
    r"(?P<tur>[CP])(?P<kullanim>\d+(?:\.\d+)?)$"
)


def opsiyon_kodu_coz(kod: str) -> OpsiyonSarti | None:
    """Opsiyon kodunu çözer; biçime uymayan kod için `None`.

    Vade koddan değil bülten satırından alınır. Kullanım fiyatı ondalık noktalıysa olduğu gibi
    (`15000.00`), noktasızsa döviz opsiyonu gösterimidir ve 1000'e bölünür (`49000` -> 49.0).
    """
    m = _OPSIYON.match(kod)
    if m is None:
        return None
    ham = m["kullanim"]
    kullanim = float(ham) if "." in ham else float(ham) / 1000
    return OpsiyonSarti(m["dayanak"], m["tur"], kullanim, m["stil"])


def vadeli_mi(s: ViopSatiri) -> bool:
    """Vadeli işlem sözleşmesi mi? Kod öneki (`F_`, esnek `TM_F_`) yeterlidir."""
    return s.kod.startswith(("F_", "TM_F_"))


def opsiyon_mu(s: ViopSatiri) -> bool:
    """Opsiyon sözleşmesi mi? Kod öneki (`O_`, esnek `TM_O_`) yeterlidir."""
    return s.kod.startswith(("O_", "TM_O_"))
