import json

import httpx
import pytest

from rasathane_ortak.tek_gonderim import GonderimHatasi as OrtakHata
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi
from capitolseeder.kanal.telegram import GonderimHatasi, gonder, httpx_istek, sahibe_bildir


def _istemci(kayit, yanit=None, durum=200):
    def isleyici(istek: httpx.Request):
        kayit.append(istek)
        return httpx.Response(durum, json=yanit or {"ok": True, "result": {"message_id": 41}})

    return httpx.Client(transport=httpx.MockTransport(isleyici))


def test_tek_hata_turu():
    assert GonderimHatasi is OrtakHata


def test_httpx_istek_json_doner():
    kayit = []
    durum, govde = httpx_istek(_istemci(kayit))("https://x/sendPhoto", {"caption": "a"},
                                                 {"photo": ("k.png", b"P", "image/png")})
    assert durum == 200 and govde["result"]["message_id"] == 41


def test_gonder_her_karti_ayri_sendphoto(tmp_path):
    kayit = []
    gidenler = [Giden("gunluk", 1, b"P1", "CAPitAL · Günün Kongre Beyanları · 22.10.2026"),
                Giden("haftalik", 1, b"P2", "CAPitAL · Haftanın Özeti · 19–23.10.2026")]
    ids = gonder("T", "@rasathane:12", "2026-10-22", gidenler, GonderimKaydi(tmp_path / "k.csv"),
                 istemci=_istemci(kayit), uyku=lambda s: None)
    assert ids == [41, 41]
    assert [i.url.path.rsplit("/", 1)[1] for i in kayit] == ["sendPhoto", "sendPhoto"]
    assert "Haftanın Özeti" in kayit[1].content.decode("utf-8", "replace")


def test_ok_false_hata(tmp_path):
    with pytest.raises(GonderimHatasi):
        gonder("T", "@r:1", "g", [Giden("gunluk", 1, b"P", "a")], GonderimKaydi(tmp_path / "k.csv"),
               istemci=_istemci([], {"ok": False, "description": "x"}, durum=400), uyku=lambda s: None)


def test_sahibe_bildir_hata_yutar():
    def bozuk(istek):
        raise httpx.ConnectError("yok")

    sahibe_bildir("T", "9", "m", istemci=httpx.Client(transport=httpx.MockTransport(bozuk)))


def test_sahibe_bildir_gonderir():
    kayit = []
    sahibe_bildir("T", "9", "metin", istemci=_istemci(kayit))
    assert kayit[0].url.path.endswith("/sendMessage")
