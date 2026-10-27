"""Haftalık raporlar: EIA petrol ve doğalgaz stokları, CFTC fon (managed money) pozisyonları.

İkisi de anahtarsız açık API: EIA için EIA_API_KEY ortamda yoksa DEMO_KEY kullanılır
(saatlik kota düşük ama günde birkaç istek için yeter).
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

_ZAMAN_ASIMI = 30
EIA_URL = "https://api.eia.gov/v2/{yol}/data/"
CFTC_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
COT_HAFTA = 156  # 3 yıl
COT_UC = 0.05

JsonAl = Callable[[str, dict[str, str]], Any]


def json_al(url: str, parametre: dict[str, str]) -> Any:
    y = requests.get(url, params=parametre, timeout=_ZAMAN_ASIMI)
    y.raise_for_status()
    return y.json()


@dataclass(frozen=True)
class EiaSeri:
    seri: str
    yol: str
    ad: str
    birim: str


PETROL = (
    EiaSeri("WCESTUS1", "petroleum/stoc/wstk", "Ham petrol (SPR hariç)", "Mn varil"),
    EiaSeri("W_EPC0_SAX_YCUOK_MBBL", "petroleum/stoc/wstk", "Cushing ham petrol", "Mn varil"),
    EiaSeri("WGTSTUS1", "petroleum/stoc/wstk", "Benzin", "Mn varil"),
    EiaSeri("WDISTUS1", "petroleum/stoc/wstk", "Distilat (dizel)", "Mn varil"),
)
DOGALGAZ = EiaSeri("NW2_EPG0_SWO_R48_BCF", "natural-gas/stor/wkly", "Doğalgaz depoları", "Bcf")


@dataclass(frozen=True)
class Stok:
    seri: EiaSeri
    donem: str  # rapor haftası (YYYY-AA-GG)
    deger: float
    degisim: float
    yil_once: float | None


def eia_stok(s: EiaSeri, al: JsonAl = json_al) -> Stok:
    veri = al(
        EIA_URL.format(yol=s.yol),
        {
            "api_key": os.environ.get("EIA_API_KEY") or "DEMO_KEY",
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": s.seri,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "60",
        },
    )
    satirlar = [r for r in veri["response"]["data"] if r.get("value") not in (None, "")]
    if len(satirlar) < 2:
        raise ValueError(f"EIA {s.seri}: yeterli veri yok")
    bolen = 1000.0 if s.birim == "Mn varil" else 1.0  # EIA bin varil verir
    degerler = [float(r["value"]) / bolen for r in satirlar]
    return Stok(
        seri=s,
        donem=str(satirlar[0]["period"]),
        deger=degerler[0],
        degisim=degerler[0] - degerler[1],
        yil_once=degerler[52] if len(degerler) > 52 else None,
    )


COT_KODLARI: tuple[tuple[str, str], ...] = (
    ("088691", "GC=F"),
    ("084691", "SI=F"),
    ("076651", "PL=F"),
    ("075651", "PA=F"),
    ("085692", "HG=F"),
    ("067651", "CL=F"),
    ("023651", "NG=F"),
    ("001602", "ZW=F"),
    ("002602", "ZC=F"),
    ("005602", "ZS=F"),
    ("083731", "KC=F"),
    ("073732", "CC=F"),
    ("080732", "SB=F"),
    ("033661", "CT=F"),
    ("057642", "LE=F"),
    ("054642", "HE=F"),
)


@dataclass(frozen=True)
class Pozisyon:
    sembol: str
    donem: str
    net: int
    degisim: int
    yuzdelik: float  # son 3 yılda bu haftanın net pozisyonunun altında kalan haftaların payı
    acik: int  # toplam açık pozisyon

    @property
    def uc(self) -> bool:
        return self.yuzdelik <= COT_UC or self.yuzdelik >= 1 - COT_UC


def cot(kod: str, sembol: str, al: JsonAl = json_al) -> Pozisyon:
    satirlar = al(
        CFTC_URL,
        {
            "$select": "report_date_as_yyyy_mm_dd,m_money_positions_long_all,"
            "m_money_positions_short_all,open_interest_all",
            "$where": f"cftc_contract_market_code='{kod}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(COT_HAFTA + 1),
        },
    )
    if len(satirlar) < 2:
        raise ValueError(f"CFTC {kod}: yeterli veri yok")
    netler = [
        int(r["m_money_positions_long_all"]) - int(r["m_money_positions_short_all"])
        for r in satirlar
    ]
    gecmis = netler[1:]
    return Pozisyon(
        sembol=sembol,
        donem=str(satirlar[0]["report_date_as_yyyy_mm_dd"])[:10],
        net=netler[0],
        degisim=netler[0] - netler[1],
        yuzdelik=sum(n < netler[0] for n in gecmis) / len(gecmis),
        acik=int(satirlar[0]["open_interest_all"]),
    )
