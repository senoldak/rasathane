"""Kanal testleri için örnek kaynak satırı ve Beyan kurucuları."""
import datetime
from dataclasses import replace

from capitolseeder.kanal.model import Beyan


def ornek_satir(**degisiklik):
    satir = {
        "id": "house_20035700_g1",
        "source_id": "house_clerk",
        "transaction_date": "2026-09-22",
        "filing_date": "2026-10-22",
        "owner": "SP",
        "ticker": "AZO",
        "asset_name": "AutoZone, Inc. Common Stock",
        "asset_type": "ST",
        "transaction_type": "Purchase",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "amount_range_label": "$15,001 - $50,000",
        "days_to_file": 30,
        "is_late": 0,
        "filer_name": "Richard W. Allen",
        "branch": "congress",
        "chamber": "house",
        "party": "R",
        "state": "GA",
        "doc_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20035700.pdf",
    }
    satir.update(degisiklik)
    return satir


_TEMEL = Beyan(
    id="x",
    ilk_gorulme="2026-10-24",
    uye="Richard W. Allen",
    parti="R",
    eyalet="GA",
    meclis="Temsilciler",
    ticker="AZO",
    varlik="AutoZone, Inc. Common Stock",
    varlik_turu="ST",
    islem="Purchase",
    tutar_alt=15001,
    tutar_ust=50000,
    tutar_etiket="$15,001 - $50,000",
    islem_tarihi=datetime.date(2026, 9, 22),
    beyan_tarihi=datetime.date(2026, 10, 22),
    gecikme=30,
    gec=False,
    belge="https://example.org/a.pdf",
)


def beyan(**degisiklik):
    return replace(_TEMEL, **degisiklik)
