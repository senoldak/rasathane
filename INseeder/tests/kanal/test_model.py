import os
from dataclasses import replace
from datetime import date

from inseeder.collectors.sec_edgar import parse_form4_beyan
from inseeder.kanal.model import beyanlar_olustur, pozisyon_degisimi

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")


def _ayristir(name: str) -> dict:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return parse_form4_beyan(f.read())


def test_beyanlar_olustur_multiple_owners():
    beyanlar = beyanlar_olustur(_ayristir("form4_coklu_sahip.xml"), "0000-26-1", date(2026, 10, 23), "https://sec/x")
    assert len(beyanlar) == 1
    b = beyanlar[0]
    assert b.unvan == "CFO"
    assert b.kisi == "0000000001"
    assert b.sembol == "KRNT"
    assert b.kod == "P"
    assert b.tutar == 46000
    assert b.dosyalama_gunu == date(2026, 10, 23)
    assert pozisyon_degisimi(b) == 0.8


def test_ceo_title_and_sale():
    beyanlar = beyanlar_olustur(_ayristir("form4_aff10b5.xml"), "0000-26-2", date(2026, 10, 23), "u")
    assert [b.kod for b in beyanlar] == ["S"]
    assert beyanlar[0].unvan == "CEO"
    assert beyanlar[0].plan_10b5_1 is True


def test_new_position_and_inconsistent():
    b = beyanlar_olustur(_ayristir("form4_coklu_sahip.xml"), "a", date(2026, 10, 23), "u")[0]
    assert pozisyon_degisimi(replace(b, sonraki_pay=b.adet)) == "yeni"
    assert pozisyon_degisimi(replace(b, sonraki_pay=b.adet - 1)) is None
    assert pozisyon_degisimi(replace(b, sonraki_pay=None)) is None


def test_empty_ticker_dropped():
    a = _ayristir("form4_coklu_sahip.xml")
    for bad in ("", "NONE", "N/A"):
        a2 = dict(a, ticker=bad)
        assert beyanlar_olustur(a2, "a", date(2026, 10, 23), "u") == []


def test_bracketed_none_ticker_dropped():
    a = dict(_ayristir("form4_coklu_sahip.xml"), ticker="[NONE]")
    assert beyanlar_olustur(a, "a", date(2026, 10, 23), "u") == []
