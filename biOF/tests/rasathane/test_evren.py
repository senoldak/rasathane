import json
import re
from datetime import date
from pathlib import Path

import httpx
import pytest

from bioseeder.rasathane.evren import (
    Sirket, ad_normallestir, ek_uygula, evren_oku, evren_olustur, evren_yaz, sponsor_eslestir,
)
from bioseeder.rasathane.http import Istemci, KaynakHatasi

ORN = Path(__file__).parent / "ornekler"


def _istemci(sayac):
    def isle(req):
        url = str(req.url)
        sayac.append(url)
        if url.endswith("company_tickers_exchange.json"):
            return httpx.Response(200, text=(ORN / "company_tickers_exchange.json").read_text())
        m = re.search(r"CIK(\d{10})\.json", url)
        if m:
            return httpx.Response(200, text=(ORN / f"submissions_{int(m.group(1))}.json").read_text())
        return httpx.Response(404)
    return Istemci(transport=httpx.MockTransport(isle), uyku=lambda s: None, sec_ua="biOF Rasathane test@ornek.com")


def _pd(t):
    return {"VKTX": 3000.0, "VRTX": 110000.0, "TINY": 30.0, "SGEN": None}.get(t)


def test_ad_normallestir():
    assert ad_normallestir("Viking Therapeutics, Inc.") == "viking therapeutics"
    assert ad_normallestir("argenx SE") == "argenx"
    assert ad_normallestir("Bristol-Myers Squibb Co") == "bristol myers squibb"
    assert ad_normallestir("Arrowhead Pharmaceuticals Inc.") == ad_normallestir("Arrowhead Pharmaceuticals")


def test_evren_olustur_suzer(tmp_path):
    ek = tmp_path / "ek.csv"
    ek.write_text("islem,ticker,ad\n", encoding="utf-8")
    s = {x.ticker: x for x in evren_olustur(_istemci([]), _pd, ek_yolu=ek)}
    assert set(s) == {"VKTX", "VRTX", "TINY", "SGEN"}
    assert s["TINY"].mikro and s["SGEN"].mikro and not s["VKTX"].mikro
    assert s["TINY"].sic == 2836


def test_eski_sic_istek_atmaz(tmp_path):
    ek = tmp_path / "ek.csv"
    ek.write_text("islem,ticker,ad\n", encoding="utf-8")
    sayac = []
    evren_olustur(_istemci(sayac), _pd, eski={1607678: 2834}, ek_yolu=ek)
    assert not any("CIK0001607678" in u for u in sayac)


def test_ekle_sic_disini_alir(tmp_path):
    ek = tmp_path / "ek.csv"
    ek.write_text("islem,ticker,ad\nekle,MSFT,\n", encoding="utf-8")
    s = {x.ticker for x in evren_olustur(_istemci([]), _pd, ek_yolu=ek)}
    assert "MSFT" in s


def test_ek_uygula(tmp_path):
    ek = tmp_path / "ek.csv"
    ek.write_text('islem,ticker,ad\ncikar,VRTX,\nesle,SGEN,"Seagen Inc."\n', encoding="utf-8")
    sirketler = [Sirket("VRTX", 1, "Vertex", "Nasdaq", 2834, 1.0), Sirket("SGEN", 2, "Seagen", "Nasdaq", 2836, 1.0)]
    kalan, esle = ek_uygula(sirketler, ek)
    assert [x.ticker for x in kalan] == ["SGEN"]
    assert esle == {"seagen": "SGEN"}
    sp = sponsor_eslestir(kalan, {"seagen genetics": "SGEN"})
    assert sp["seagen"].ticker == "SGEN"
    assert sp["seagen genetics"].ticker == "SGEN"


def test_evren_yaz_oku(tmp_path):
    yol = tmp_path / "evren.csv"
    s = [Sirket("VKTX", 1607678, "Viking Therapeutics, Inc.", "Nasdaq", 2834, 3000.0),
         Sirket("SGEN", 3, "Seagen", "Nasdaq", 2836, None)]
    evren_yaz(s, yol, bugun=date(2026, 10, 25))
    assert evren_oku(yol, bugun=date(2026, 11, 1)) == sorted(s, key=lambda x: x.ticker)


def test_evren_eski_hata(tmp_path):
    yol = tmp_path / "evren.csv"
    evren_yaz([], yol, bugun=date(2026, 9, 1))
    with pytest.raises(KaynakHatasi):
        evren_oku(yol, bugun=date(2026, 10, 17))
    with pytest.raises(KaynakHatasi):
        evren_oku(tmp_path / "yok.csv", bugun=date(2026, 10, 17))
