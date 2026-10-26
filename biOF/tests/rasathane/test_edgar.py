from datetime import date
from pathlib import Path

import httpx
import pytest

from bioseeder.rasathane.edgar import Bildirim, bulten_metni, guncel_8k, gunluk_8k
from bioseeder.rasathane.http import Istemci, KaynakHatasi

ORN = Path(__file__).parent / "ornekler"


def _istemci(yanit_fn, istekler=None):
    def isle(req):
        if istekler is not None:
            istekler.append(req)
        return yanit_fn(req)
    return Istemci(transport=httpx.MockTransport(isle), uyku=lambda s: None, sec_ua="biOF Rasathane test@ornek.com")


def test_gunluk_dizin():
    istekler = []
    ist = _istemci(lambda r: httpx.Response(200, text=(ORN / "form.20261023.idx").read_text()), istekler)
    b = gunluk_8k(ist, date(2026, 10, 23))
    assert "daily-index/2026/QTR4/form.20261023.idx" in str(istekler[0].url)
    assert [(x.cik, x.erisim) for x in b] == [(1607678, "0001607678-26-000045"), (873303, "0000873303-26-000101")]
    assert b[1].ad == "SAREPTA THERAPEUTICS, INC." and b[0].tarih == date(2026, 10, 23)
    assert b[0].baglanti == ("https://www.sec.gov/Archives/edgar/data/1607678/000160767826000045/"
                             "0001607678-26-000045-index.htm")


def test_gunluk_dizin_404():
    ist = _istemci(lambda r: httpx.Response(404))
    with pytest.raises(KaynakHatasi) as e:
        gunluk_8k(ist, date(2026, 10, 23))
    assert e.value.durum == 404


def _atom(req):
    if req.url.params.get("start") == "0":
        return httpx.Response(200, text=(ORN / "current_8k.atom").read_text())
    return httpx.Response(200, text='<feed xmlns="http://www.w3.org/2005/Atom"></feed>')


def test_guncel_imlec():
    b, imlec = guncel_8k(_istemci(_atom), "0000873303-26-000102")
    assert [x.erisim for x in b] == ["0001607678-26-000046"]
    assert imlec == "0001607678-26-000046"
    assert b[0].cik == 1607678 and b[0].ad == "VIKING THERAPEUTICS INC"


def test_guncel_imlecsiz_tek_sayfa():
    istekler = []
    b, imlec = guncel_8k(_istemci(_atom, istekler), None)
    assert len(b) == 3 and len(istekler) == 1 and imlec == "0001607678-26-000046"


def test_guncel_imlec_bulunamazsa_sayfalar():
    istekler = []
    b, _ = guncel_8k(_istemci(_atom, istekler), "0009999999-26-000001", en_fazla_sayfa=3)
    assert len(b) == 3 and len(istekler) == 2  # ikinci sayfa boş → durur


def test_bulten_metni():
    ist = _istemci(lambda r: httpx.Response(200, text=(ORN / "dosya_8k.txt").read_text()))
    b = Bildirim("0001607678-26-000045", 1607678, "VIKING", date(2026, 10, 23))
    m = bulten_metni(ist, b)
    assert m.startswith("Viking Therapeutics Announces Topline Results from Phase 3 VENTURE Trial")
    assert "SAN DIEGO & NEW YORK" in m and "NCT06000001" in m
    assert "Item 8.01" not in m and "begin 644" not in m
