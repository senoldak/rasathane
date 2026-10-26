import datetime

import httpx
import pytest

from capitolseeder.kanal import kaynak
from capitolseeder.kanal.kaynak import VeriHatasi, dogrula, indir, kongre_beyanlari
from capitolseeder.kanal.model import hisse_mi, kisa_ad, kisa_sirket, kisa_tutar
from tests.kanal.yardimci import beyan, ornek_satir


def test_kongre_disi_ve_yinelenen_elenir():
    s = [ornek_satir(id="a"), ornek_satir(id="a"), ornek_satir(id="b", branch="executive", chamber=None)]
    assert [b.id for b in kongre_beyanlari(s, "2026-10-24")] == ["a"]


def test_meclis_ve_parti():
    b = kongre_beyanlari([ornek_satir(chamber="senate", party="D")], "x")[0]
    assert (b.meclis, b.parti) == ("Senato", "D")
    assert b.islem_tarihi == datetime.date(2026, 9, 22)
    assert b.ilk_gorulme == "x"


def test_bos_alanlar_bos_metne_doner():
    b = kongre_beyanlari([ornek_satir(ticker=None, asset_type=None, amount_range_high=None)], "x")[0]
    assert (b.ticker, b.varlik_turu, b.tutar_ust) == ("", "", 0)


def test_hisse_mi():
    assert hisse_mi(beyan(varlik_turu="ST")) and hisse_mi(beyan(varlik_turu=""))
    assert hisse_mi(beyan(varlik_turu="Stock")) and hisse_mi(beyan(varlik_turu="CS"))
    assert not hisse_mi(beyan(varlik_turu="GS")) and not hisse_mi(beyan(varlik_turu="OP"))
    assert not hisse_mi(beyan(islem="Exchange")) and not hisse_mi(beyan(ticker=""))


def test_yon():
    assert beyan(islem="Purchase").yon == "Alış"
    assert beyan(islem="Sale (Partial)").yon == "Satış"
    assert beyan(islem="Sale (Full)").yon == "Satış"
    assert beyan(islem="Exchange").yon is None


def test_kisa_adlar():
    assert kisa_ad("Michael T. McCaul") == "M. McCaul"
    assert kisa_ad("Scott Scott Franklin") == "S. Franklin"
    assert kisa_ad("Thomas H. Kean Jr") == "T. Kean Jr"
    assert kisa_sirket("AutoZone, Inc. Common Stock") == "AutoZone"
    assert kisa_sirket("NVIDIA Corporation - Common Stock") == "NVIDIA"
    assert kisa_sirket("Berkshire Hathaway Inc. New") == "Berkshire Hathaway"
    assert kisa_sirket("VALVOLINE INC") == "Valvoline"
    assert len(kisa_sirket("MUELLER WATER PRODUCTS INCORPORATED HOLDINGS")) <= 18
    assert kisa_tutar(100001, 250000) == "$100k–250k"
    assert kisa_tutar(1001, 15000) == "$1k–15k"
    assert kisa_tutar(1000001, 5000000) == "$1M–5M"
    assert kisa_tutar(50000001, 0) == "$50M+"


def test_dogrula_hatalari():
    bugun = datetime.date(2026, 10, 24)
    for bozuk in (
        {},
        [],
        [ornek_satir(branch="executive")],
        [ornek_satir(filing_date="2026-10-01")],
        [ornek_satir()] * 18 + [ornek_satir(filer_name="")] * 2,
    ):
        with pytest.raises(VeriHatasi):
            dogrula(bozuk, bugun)
    dogrula([ornek_satir(filing_date="2026-10-22")], bugun)


def test_indir_uc_kez_dener(monkeypatch):
    monkeypatch.setattr(kaynak.time, "sleep", lambda s: None)
    cagri = {"n": 0}

    def isleyici(istek):
        cagri["n"] += 1
        if cagri["n"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, json=[ornek_satir()])

    istemci = httpx.Client(transport=httpx.MockTransport(isleyici))
    assert len(indir(istemci=istemci)) == 1 and cagri["n"] == 3

    hep_hata = httpx.Client(transport=httpx.MockTransport(lambda i: httpx.Response(503)))
    with pytest.raises(VeriHatasi):
        indir(istemci=hep_hata)


def test_tahvil_ve_mevduat_hisse_sayilmaz():
    assert not hisse_mi(beyan(ticker="US-TBILL", varlik_turu=""))
    assert not hisse_mi(beyan(ticker="JPM", varlik_turu="CS", varlik="JPMorgan Chase Bank CTF DEP 4.200%"))
    assert not hisse_mi(beyan(ticker="ORCL", varlik="Oracle Corp 4.9% 02/06/2033"))
    assert not hisse_mi(beyan(ticker="GOOGL", varlik="Alphabet Note Coupon 4.80000%"))
    assert not hisse_mi(beyan(ticker="T", varlik="AT&T Inc due 2030"))
    assert hisse_mi(beyan(ticker="BRK.B", varlik="Berkshire Hathaway Inc. New"))
    assert hisse_mi(beyan(ticker="NOTE", varlik="FiscalNote Holdings Inc"))


def test_tek_bozuk_tarih_gunu_durdurmaz():
    bugun = datetime.date(2026, 10, 24)
    dogrula([ornek_satir(filing_date="2026-10-22")] * 30 + [ornek_satir(filing_date="bozuk")], bugun)


def test_gelecek_tarihli_yazim_hatasi_bayat_kaynagi_gizlemez():
    bugun = datetime.date(2026, 10, 24)
    with pytest.raises(VeriHatasi):
        dogrula([ornek_satir(filing_date="2026-10-01")] * 30 + [ornek_satir(filing_date="2062-10-01")], bugun)
