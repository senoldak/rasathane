"""Merkez bankalarının altın rezervi (IMF International Liquidity, GOLD35P_REVS), ton cinsinden.

Kaynak: IMF, International Liquidity (IL). IMF verisi XDR cinsindendir ve 35 SDR/ons sabit değerle
verilir; ton değeri bu iki sabitle bizim tarafımızdan hesaplanır ve sayfada bu açıkça yazılır.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any

import requests
from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz, seri_yaz

log = logging.getLogger("emtia")

BOLUM = "emtia"
SAYFA = "merkez"
_URL = (
    "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IL,13.0.1/"
    "{ulkeler}.GOLD35P_REVS.*.M?startPeriod={bas}&format=structurespecificdata"
)
_KAYNAK = Kaynak(
    "IMF, International Liquidity (IL)", "https://data.imf.org/en/datasets//IMF.STA:IL"
)
ULKELER: dict[str, str] = {
    "CHN": "Çin",
    "USA": "ABD",
    "DEU": "Almanya",
    "ITA": "İtalya",
    "FRA": "Fransa",
    "RUS": "Rusya",
    "JPN": "Japonya",
    "IND": "Hindistan",
    "POL": "Polonya",
    "TUR": "Türkiye",
    "GBR": "Birleşik Krallık",
    "CHE": "İsviçre",
}
ONS_BASINA_SDR = 35.0
TROY_ONS_TON = 32150.7466  # 1 ton = 32.150,7466 troy ons
_SERI = re.compile(r"<(?:generic:)?Series ([^>]*)>(.*?)</(?:generic:)?Series>", re.DOTALL)
_OBS = re.compile(r'TIME_PERIOD="(\d{4})-M(\d{2})" OBS_VALUE="([^"]+)"')
_ULKE = re.compile(r'COUNTRY="(\w+)"')


def ton_cevir(xdr: float) -> float:
    return xdr / ONS_BASINA_SDR / TROY_ONS_TON


def ayikla(xml: str) -> dict[str, list[tuple[datetime.date, float]]]:
    """Ülke kodu → (ay, ton) listesi, tarihe göre sıralı."""
    sonuc: dict[str, list[tuple[datetime.date, float]]] = {}
    for m in _SERI.finditer(xml):
        ulke = _ULKE.search(m.group(1))
        if ulke is None:
            continue
        noktalar = [
            (datetime.date(int(y), int(a), 1), ton_cevir(float(v)))
            for y, a, v in _OBS.findall(m.group(2))
        ]
        if noktalar:
            sonuc[ulke.group(1)] = sorted(noktalar)
    return sonuc


def _onceki_yil(s: list[tuple[datetime.date, float]], son: datetime.date) -> float | None:
    return next((v for d, v in s if d.year == son.year - 1 and d.month == son.month), None)


def aktar(kok: Path, simdi: datetime.datetime) -> Path | None:
    """IMF'den çeker, ülke serilerini ve tablo sayfasını yazar. Hata olursa None döner (kartlar etkilenmez)."""
    try:
        yanit = requests.get(_URL.format(ulkeler="+".join(ULKELER), bas="2021-01"), timeout=90)
        yanit.raise_for_status()
        seriler = ayikla(yanit.text)
    except Exception as hata:  # IMF erişimi bu akışı durdurmamalı
        log.warning("IMF altın rezervi alınamadı: %s", type(hata).__name__)
        return None

    satirlar: list[dict[str, Any]] = []
    for kod, ad in ULKELER.items():
        s = seriler.get(kod)
        if not s:
            continue
        anahtar = f"imf-{kod}"
        seri_yaz(kok, BOLUM, anahtar, s, ad=f"{ad} altın rezervi", birim="ton")
        son_donem, son = s[-1]
        onceki_ay = s[-2][1] if len(s) > 1 else None
        onceki_yil = _onceki_yil(s, son_donem)
        satirlar.append(
            {
                "ad": ad,
                "donem": son_donem.strftime("%Y-%m"),
                "ton": son,
                "aylik": son - onceki_ay if onceki_ay is not None else None,
                "yillik": son / onceki_yil - 1 if onceki_yil else None,
                "seri": anahtar,
            }
        )
    if not satirlar:
        return None
    return Path(
        sayfa_yaz(
            kok,
            BOLUM,
            SAYFA,
            baslik="Merkez bankaları altın rezervi",
            aciklama="Seçilmiş ülkelerin resmî altın rezervi (ton). Son ay verisi IMF tarafından düzeltilebilir.",
            guncellendi=simdi,
            kaynaklar=[_KAYNAK],
            sutunlar=[
                Sutun("ad", "Ülke", "metin"),
                Sutun("donem", "Dönem", "metin"),
                Sutun("ton", "Ton", "sayi", 0),
                Sutun("aylik", "Son ay (ton)", "sayi", 1),
                Sutun("yillik", "1 yıl", "yuzde", 1),
            ],
            satirlar=satirlar,
        )
    )
