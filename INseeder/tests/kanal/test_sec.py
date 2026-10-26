import os
from datetime import date

import httpx
import pytest

from inseeder.kanal.sec import KanalHatasi, SecIstemcisi

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
with open(os.path.join(FIXTURES, "submission_sample.txt"), encoding="utf-8") as _f:
    SUBMISSION = _f.read()

GUN = date(2026, 10, 23)
INDEX_URL = "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.20261023.idx"


def _index(n: int, extra: str = "") -> str:
    head = "Description:           Daily Index of EDGAR Dissemination Feed by Form Type\n\nForm Type   Company Name   CIK   Date Filed  File Name\n" + "-" * 80 + "\n"
    rows = "".join(
        f"4           COMPANY {i:<40} {1000 + i:<10} 20261023    edgar/data/{1000 + i}/0001234567-26-{i:06d}.txt\n"
        for i in range(n)
    )
    return head + rows + extra


class Kayitci:
    def __init__(self):
        self.uykular = []

    def __call__(self, s):
        self.uykular.append(s)


def _istemci(handler, uyku=None):
    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "Test test@example.com"})
    return SecIstemcisi(client, uyku=uyku or Kayitci())


def test_gun_isle_parses_index_and_filings():
    dup = "4           COMPANY 0  1000  20261023    edgar/data/1000/0001234567-26-000000.txt\n"
    amend = "4/A         COMPANY X  9999  20261023    edgar/data/9999/0009999999-26-000001.txt\n"
    istekler = []

    def handler(req):
        istekler.append(str(req.url))
        if str(req.url) == INDEX_URL:
            return httpx.Response(200, text=_index(120, dup + amend))
        return httpx.Response(200, text=SUBMISSION)

    sonuc = _istemci(handler).gun_isle(GUN)
    assert sonuc.dizin_var is True
    assert sonuc.toplam == 120
    assert sonuc.okunan == 120
    assert sonuc.hatali == 0
    assert len(sonuc.beyanlar) == 120
    assert not any("0009999999" in u for u in istekler)
    b = sonuc.beyanlar[0]
    assert b.dosyalama_gunu == GUN
    assert b.sec_url == "https://www.sec.gov/Archives/edgar/data/1000/000123456726000000/0001234567-26-000000-index.htm"
    assert b.accession_no == "0001234567-26-000000"


def test_holiday_404_returns_empty():
    sonuc = _istemci(lambda req: httpx.Response(404)).gun_isle(date(2026, 12, 25))
    assert sonuc.dizin_var is False
    assert sonuc.toplam == 0
    assert sonuc.beyanlar == []


def test_workday_404_retries_then_fails():
    uyku = Kayitci()
    with pytest.raises(KanalHatasi):
        _istemci(lambda req: httpx.Response(404), uyku).gun_isle(GUN)
    assert uyku.uykular.count(1200) == 9


def test_workday_404_no_wait_returns_empty():
    # Doldurmada plansız SEC kapanışı (ör. yas günü) kanalı günlerce tıkamamalı.
    uyku = Kayitci()
    sonuc = _istemci(lambda req: httpx.Response(404), uyku).gun_isle(GUN, bekle_404=False)
    assert sonuc.dizin_var is False
    assert 1200 not in uyku.uykular


def test_workday_404_then_ok():
    sayac = {"n": 0}

    def handler(req):
        if str(req.url) == INDEX_URL:
            sayac["n"] += 1
            if sayac["n"] <= 2:
                return httpx.Response(404)
            return httpx.Response(200, text=_index(100))
        return httpx.Response(200, text=SUBMISSION)

    sonuc = _istemci(handler).gun_isle(GUN)
    assert sonuc.toplam == 100


def test_server_error_retries_three_times():
    sayac = {"n": 0}

    def handler(req):
        sayac["n"] += 1
        return httpx.Response(503)

    with pytest.raises(KanalHatasi):
        _istemci(handler).gun_isle(GUN)
    assert sayac["n"] == 3


def test_too_few_filings_fails():
    def handler(req):
        if str(req.url) == INDEX_URL:
            return httpx.Response(200, text=_index(50))
        return httpx.Response(200, text=SUBMISSION)

    with pytest.raises(KanalHatasi, match="50"):
        _istemci(handler).gun_isle(GUN)


def test_too_many_failures_fails():
    def handler(req):
        url = str(req.url)
        if url == INDEX_URL:
            return httpx.Response(200, text=_index(120))
        i = int(url.rsplit("-", 1)[1].split(".")[0])
        if i < 13:
            return httpx.Response(500)
        return httpx.Response(200, text=SUBMISSION)

    with pytest.raises(KanalHatasi):
        _istemci(handler).gun_isle(GUN)


def test_few_failures_tolerated():
    def handler(req):
        url = str(req.url)
        if url == INDEX_URL:
            return httpx.Response(200, text=_index(120))
        if url.endswith("000001.txt"):
            return httpx.Response(200, text="garbage")
        return httpx.Response(200, text=SUBMISSION)

    sonuc = _istemci(handler).gun_isle(GUN)
    assert sonuc.hatali == 1
    assert sonuc.okunan == 119


def test_user_agent_header_sent():
    ua = []

    def handler(req):
        ua.append(req.headers.get("User-Agent"))
        if str(req.url) == INDEX_URL:
            return httpx.Response(200, text=_index(100))
        return httpx.Response(200, text=SUBMISSION)

    _istemci(handler).gun_isle(GUN)
    assert set(ua) == {"Test test@example.com"}


def test_forbidden_mentions_user_agent():
    with pytest.raises(KanalHatasi, match="SEC_USER_AGENT"):
        _istemci(lambda req: httpx.Response(403)).gun_isle(GUN)
