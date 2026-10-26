"""Telegram Bot API: kartları konuya tek tek gönderir, hataları sahibine bildirir."""
import logging
import time
from typing import Any, Callable, Optional

import httpx

from rasathane_ortak.tek_gonderim import (
    Giden,
    GonderimHatasi,
    GonderimKaydi,
    Istek,
    sirayla_gonder,
)

logger = logging.getLogger("capitolseeder.kanal")

API = "https://api.telegram.org/bot{token}/{yontem}"

__all__ = ["GonderimHatasi", "gonder", "httpx_istek", "sahibe_bildir"]


def httpx_istek(istemci: httpx.Client) -> Istek:
    """rasathane_ortak.tek_gonderim için çok parçalı POST; (durum, JSON gövde) döner."""
    def istek(url: str, alanlar: dict, dosyalar: dict) -> tuple[int, dict]:
        yanit = istemci.post(url, data=alanlar, files=dosyalar)
        try:
            return yanit.status_code, yanit.json()
        except ValueError:
            return yanit.status_code, {"ok": False, "description": yanit.text[:200]}
    return istek


def gonder(
    token: str,
    hedef: str,
    gun: str,
    gidenler: list[Giden],
    kayit: GonderimKaydi,
    istemci: Optional[httpx.Client] = None,
    uyku: Callable[[float], None] = time.sleep,
) -> list[int]:
    """Kartları sırayla ayrı sendPhoto mesajları olarak gönderir; gönderilmiş kartları atlar."""
    istemci = istemci or httpx.Client(timeout=60.0)
    return sirayla_gonder(httpx_istek(istemci), token, hedef, gun, gidenler, kayit, uyku=uyku)


def _istek(istemci: httpx.Client, token: str, yontem: str, **kw: Any) -> Any:
    try:
        yanit = istemci.post(API.format(token=token, yontem=yontem), **kw)
        veri = yanit.json()
    except (httpx.HTTPError, ValueError) as e:
        raise GonderimHatasi(f"{yontem} isteği başarısız: {type(e).__name__}") from None
    if not veri.get("ok"):
        raise GonderimHatasi(f"{yontem} reddedildi: {veri.get('description')}")
    return veri["result"]


def sahibe_bildir(token: str, sahip_id: str, metin: str, istemci: Optional[httpx.Client] = None) -> None:
    if not token or not sahip_id:
        logger.error("Sahibe bildirilemedi (token ya da sahip kimliği yok): %s", metin)
        return
    istemci = istemci or httpx.Client(timeout=30.0)
    try:
        _istek(istemci, token, "sendMessage", data={"chat_id": sahip_id, "text": metin})
    except GonderimHatasi as e:
        logger.error("Sahibe bildirilemedi: %s (%s)", metin, e)
