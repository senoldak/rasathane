"""Borsa İstanbul pay piyasası günlük bülteni (thb*.zip) okuyucusu."""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PaySatiri:
    kod: str
    ad: str
    tip: str
    onceki_kapanis: float
    kapanis: float
    degisim_yuzde: float
    en_iyi_alis: float
    en_iyi_satis: float
    aof: float
    hacim_tl: float
    adet: int
    islem_sayisi: int


def _sayi(metin: str) -> float:
    metin = metin.strip()
    return float(metin) if metin else 0.0


def pay_bulteni_csv_oku(csv_metin: str) -> tuple[date, list[PaySatiri]]:
    """CSV metnini okur: `;` ayraç, ilk iki satır (TR/EN) başlık."""
    okuyucu = csv.reader(io.StringIO(csv_metin), delimiter=";")
    basliklar = next(okuyucu)
    next(okuyucu)  # İngilizce başlık satırı
    sutun = {ad: i for i, ad in enumerate(basliklar)}
    i_tarih = sutun["TARIH"]
    i_kod = sutun["ISLEM  KODU"]
    i_ad = sutun["BULTEN ADI"]
    i_tip = sutun["ENSTRUMAN TIPI"]
    i_onc = sutun["ONCEKI KAPANIS FIYATI"]
    i_kap = sutun["KAPANIS FIYATI"]
    i_deg = sutun["DEGISIM (%)"]
    i_alis = sutun["BEKLEYEN EN IYI ALIS"]
    i_satis = sutun["BEKLEYEN EN IYI SATIS"]
    i_aof = sutun["A.O.F"]
    i_hacim = sutun["TOPLAM ISLEM HACMI"]
    i_adet = sutun["TOPLAM ISLEM ADEDI"]
    i_islem = sutun["TOPLAM SOZLESME SAYISI"]

    gunler: set[date] = set()
    satirlar: list[PaySatiri] = []
    for s in okuyucu:
        if not s or not any(s):
            continue
        gunler.add(date.fromisoformat(s[i_tarih].strip()))
        satirlar.append(
            PaySatiri(
                kod=s[i_kod].strip(),
                ad=s[i_ad].strip(),
                tip=s[i_tip].strip(),
                onceki_kapanis=_sayi(s[i_onc]),
                kapanis=_sayi(s[i_kap]),
                degisim_yuzde=_sayi(s[i_deg]),
                en_iyi_alis=_sayi(s[i_alis]),
                en_iyi_satis=_sayi(s[i_satis]),
                aof=_sayi(s[i_aof]),
                hacim_tl=_sayi(s[i_hacim]),
                adet=int(_sayi(s[i_adet])),
                islem_sayisi=int(_sayi(s[i_islem])),
            )
        )
    if len(gunler) != 1:
        raise ValueError(f"bültende tek tarih beklenirdi, bulunan: {sorted(gunler)}")
    return next(iter(gunler)), satirlar


def pay_bulteni_oku(zip_bayt: bytes) -> tuple[date, list[PaySatiri]]:
    """Zip içindeki tek CSV'yi okur.

    Dosya düz ASCII (Türkçe karakter yok); latin-1 ile çözmek her bayt için güvenlidir.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bayt)) as z:
        adlar = [a for a in z.namelist() if a.lower().endswith(".csv")]
        if len(adlar) != 1:
            raise ValueError(f"zip içinde tek CSV beklenirdi, bulunan: {adlar}")
        metin = z.read(adlar[0]).decode("latin-1")
    return pay_bulteni_csv_oku(metin)
