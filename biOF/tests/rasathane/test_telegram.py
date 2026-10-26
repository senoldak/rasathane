import json
from datetime import date

import httpx
import pytest

from bioseeder.rasathane.ayar import Ayar
from rasathane_ortak.tek_gonderim import Giden, GonderimHatasi, GonderimKaydi
from bioseeder.rasathane.telegram import Telegram, TelegramHatasi

AYAR = Ayar(bot_token="TOKEN", sahip_id="99", hedef_sohbet="@rasathane", hedef_konu=42, gonderim_acik=True)


def _tg(yanitlar, istekler):
    sira = list(yanitlar)

    def isle(req):
        istekler.append(req)
        return sira.pop(0) if len(sira) > 1 else sira[0]
    return Telegram(AYAR, transport=httpx.MockTransport(isle), uyku=lambda s: None)


OK = httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})


def _alan(req, ad):
    govde = req.content.decode("utf-8", "replace")
    parca = govde.split(f'name="{ad}"', 1)[1]
    return parca.split("\r\n\r\n", 1)[1].split("\r\n--", 1)[0]


def _gidenler(n):
    return [Giden(f"k{i}", 1, b"P%d" % i, f"biOF · Kart {i} · 23.10.2026") for i in range(n)]


def test_her_kart_ayri_sendphoto(tmp_path):
    istekler = []
    ids = _tg([OK], istekler).sirayla("2026-10-23", _gidenler(2), GonderimKaydi(tmp_path / "k.csv"))
    assert ids == [7, 7]
    assert [r.url.path.rsplit("/", 1)[1] for r in istekler] == ["sendPhoto", "sendPhoto"]
    assert _alan(istekler[0], "chat_id") == "@rasathane"
    assert _alan(istekler[0], "message_thread_id") == "42"
    assert _alan(istekler[1], "caption") == "biOF · Kart 1 · 23.10.2026"


def test_telegram_hatasi_istisna(tmp_path):
    istekler = []
    hata = httpx.Response(400, json={"ok": False, "description": "Bad Request: TOPIC_CLOSED"})
    with pytest.raises(GonderimHatasi):
        _tg([hata], istekler).sirayla("g", _gidenler(1), GonderimKaydi(tmp_path / "k.csv"))


def test_hedef_yoksa_hata(tmp_path):
    tg = Telegram(Ayar(bot_token=None, sahip_id=None, hedef_sohbet=None, hedef_konu=None, gonderim_acik=True))
    with pytest.raises(TelegramHatasi):
        tg.sirayla("g", _gidenler(1), GonderimKaydi(tmp_path / "k.csv"))


def test_sahibe():
    istekler = []
    _tg([OK], istekler).sahibe("hata")
    assert istekler[0].url.path == "/botTOKEN/sendMessage"
    assert json.loads(istekler[0].content)["chat_id"] == "99"


def test_sahibe_token_yoksa_sessiz():
    t = Telegram(Ayar(None, None, None, None, False), transport=httpx.MockTransport(lambda r: 1 / 0))
    t.sahibe("x")
