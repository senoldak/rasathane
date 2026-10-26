from datetime import date

from inseeder.kanal.model import Beyan

_sayac = {"n": 0}


def beyan(sembol="KRNT", tutar=200_000.0, kod="P", kisi=None, unvan="CEO",
          gun=date(2026, 10, 23), plan=False, sirket=None, sonraki_pay=None):
    _sayac["n"] += 1
    n = _sayac["n"]
    adet = tutar / 10.0
    return Beyan(
        dosyalama_gunu=gun,
        accession_no=f"0000000000-26-{n:06d}",
        sembol=sembol,
        sirket=sirket or f"{sembol} Holdings Inc",
        kisi=kisi or f"{n:010d}",
        unvan=unvan,
        kod=kod,
        adet=adet,
        ort_fiyat=10.0,
        tutar=tutar,
        sonraki_pay=sonraki_pay if sonraki_pay is not None else adet * 3,
        plan_10b5_1=plan,
        sec_url=f"https://www.sec.gov/Archives/edgar/data/1/{n}/x-index.htm",
    )
