"""Kanalın beyan modeli: bir Form 4'teki bir işlem kodunun toplamı."""
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Union

from inseeder.engine.scorer import _match_role

KIDEM = ["CEO", "CFO", "COO/President", "Director", "Officer", "10% Owner", "Other"]
UNVAN_TR = {
    "CEO": "CEO",
    "CFO": "CFO",
    "COO/President": "COO/Başkan",
    "Director": "Direktör",
    "Officer": "Yönetici",
    "10% Owner": "%10 ortak",
    "Other": "Diğer",
}
GECERSIZ_SEMBOL = {"", "NONE", "N/A", "NA"}


@dataclass(frozen=True)
class Beyan:
    dosyalama_gunu: date
    accession_no: str
    sembol: str
    sirket: str
    kisi: str
    unvan: str
    kod: str
    adet: float
    ort_fiyat: float
    tutar: float
    sonraki_pay: Optional[float]
    plan_10b5_1: bool
    sec_url: str


def _unvan(owners: List[Dict[str, Any]]) -> str:
    roller = [
        _match_role(o["title"], o["is_officer"], o["is_director"], o["is_ten_percent"])[0]
        for o in owners
    ] or ["Other"]
    return UNVAN_TR[min(roller, key=KIDEM.index)]


def beyanlar_olustur(ayristirma: Dict[str, Any], accession_no: str,
                     dosyalama_gunu: date, sec_url: str) -> List[Beyan]:
    sembol = ayristirma["ticker"].strip().strip("[]").strip().upper()
    if sembol in GECERSIZ_SEMBOL:
        return []
    owners = ayristirma["owners"]
    kisi = min((o["cik"] for o in owners if o["cik"]), default=accession_no)
    unvan = _unvan(owners)
    return [
        Beyan(
            dosyalama_gunu=dosyalama_gunu,
            accession_no=accession_no,
            sembol=sembol,
            sirket=ayristirma["company_name"],
            kisi=kisi,
            unvan=unvan,
            kod=kod,
            adet=agg["shares"],
            ort_fiyat=agg["avg_price"],
            tutar=agg["value"],
            sonraki_pay=agg["owned_after"],
            plan_10b5_1=ayristirma["plan_10b5_1"],
            sec_url=sec_url,
        )
        for kod, agg in ayristirma["by_code"].items()
    ]


def pozisyon_degisimi(b: Beyan) -> Union[float, str, None]:
    """Alım sonrası pozisyon artışı oranı; önceki pay 0 ise 'yeni', tutarsızsa None."""
    if b.sonraki_pay is None:
        return None
    onceki = b.sonraki_pay - b.adet
    if onceki < 0:
        return None
    if onceki == 0:
        return "yeni"
    return b.adet / onceki
