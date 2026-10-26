import json

import httpx

from inseeder.kanal.telegram import TelegramIstemcisi


class Yakalayici:
    def __init__(self, yanitlar=None):
        self.istekler = []
        self.yanitlar = list(yanitlar or [])

    def __call__(self, req):
        self.istekler.append(req)
        if self.yanitlar:
            return self.yanitlar.pop(0)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 5}})

    def istemci(self):
        return TelegramIstemcisi(httpx.Client(transport=httpx.MockTransport(self)), "TOKEN", uyku=lambda s: None)


def test_istek_sends_multipart_and_returns_json():
    y = Yakalayici()
    durum, govde = y.istemci().istek("https://api.telegram.org/botTOKEN/sendPhoto",
                                     {"chat_id": "@rasathane", "caption": "açıklama"},
                                     {"photo": ("kart.png", b"\x89PNG", "image/png")})
    assert durum == 200 and govde["result"]["message_id"] == 5
    govde_metni = y.istekler[0].content.decode("utf-8", errors="replace")
    assert "açıklama" in govde_metni and "kart.png" in govde_metni


def test_istek_non_json_body():
    y = Yakalayici([httpx.Response(502, text="Bad gateway")])
    durum, govde = y.istemci().istek("https://x/sendPhoto", {}, {})
    assert durum == 502 and govde["ok"] is False and "Bad gateway" in govde["description"]


def test_owner_message():
    y = Yakalayici()
    y.istemci().sahibe_yaz("99", "hata")
    assert y.istekler[0].url.path.endswith("/sendMessage")
    assert json.loads(y.istekler[0].content) == {"chat_id": "99", "text": "hata"}


def test_owner_message_failure_is_swallowed():
    y = Yakalayici([httpx.Response(500, text="x")])
    y.istemci().sahibe_yaz("99", "hata")
