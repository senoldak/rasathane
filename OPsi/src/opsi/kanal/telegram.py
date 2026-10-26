# src/opsi/kanal/telegram.py
"""Telegram Bot API: kartları tek tek (sendPhoto) gönderir, sahibine hata yazar.

Hedef biçimi mecmua ile aynı: "@grup:konu_kimliği" (forum konusu) ya da "@kanal".
"""

import logging
import time
from typing import Any

import requests
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi, sirayla_gonder

_API = "https://api.telegram.org/bot{token}/{yontem}"
_ZAMAN_ASIMI = 60
_DENEME = 2  # ilk deneme + bir yeniden deneme
_MAKS_BEKLEME = 60.0
_ARA = 1.5  # kartlar arası bekleme (sn)

log = logging.getLogger("opsi.kanal")


def _cagir(token: str, yontem: str, veri: dict[str, Any], dosyalar: dict[str, Any]) -> None:
    """Yalnız isteğin Telegram'a ulaşmadığı kesin olan durumlarda yeniden dener.

    Bağlantı kurulamadıysa ya da 429 (retry_after kadar beklenir) döndüyse bir kez daha;
    okuma zaman aşımı yeniden denenmez (albüm zaten yayımlanmış olabilir).
    """
    hata = ""
    for deneme in range(_DENEME):
        try:
            y = requests.post(
                _API.format(token=token, yontem=yontem),
                data=veri,
                files=dosyalar or None,
                timeout=_ZAMAN_ASIMI,
            )
            govde = y.json()
        except requests.ConnectionError as e:
            hata = str(e)
            continue
        except (requests.RequestException, ValueError) as e:
            raise RuntimeError(f"Telegram {yontem} başarısız: {e}") from e
        if govde.get("ok"):
            return
        hata = str(govde.get("description") or f"HTTP {y.status_code}")
        bekle = (govde.get("parameters") or {}).get("retry_after")
        if govde.get("error_code") == 429 and bekle and deneme + 1 < _DENEME:
            time.sleep(min(float(bekle), _MAKS_BEKLEME))
            continue
        break
    raise RuntimeError(f"Telegram {yontem} başarısız: {hata}")


def requests_istek(
    url: str, alanlar: dict[str, str], dosyalar: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    """rasathane_ortak.tek_gonderim için çok parçalı POST.

    Yalnız bağlantı hiç kurulamadıysa bir kez daha dener; okuma zaman aşımı yeniden denenmez
    (kart zaten yayımlanmış olabilir).
    """
    for deneme in range(_DENEME):
        try:
            y = requests.post(url, data=alanlar, files=dosyalar or None, timeout=_ZAMAN_ASIMI)
        except requests.ConnectionError:
            if deneme + 1 == _DENEME:
                raise
            continue
        try:
            return y.status_code, y.json()
        except ValueError:
            return y.status_code, {"ok": False, "description": f"HTTP {y.status_code}"}
    raise AssertionError("ulaşılmaz")


def gonder(
    token: str, hedef: str, gun: str, gidenler: list[Giden], kayit: GonderimKaydi
) -> list[int]:
    """Kartları sırayla ayrı sendPhoto mesajları olarak gönderir; gönderilmiş kartları atlar."""
    return sirayla_gonder(requests_istek, token, hedef, gun, gidenler, kayit, ara=_ARA)


def sahibe_yaz(token: str, sahip_id: str, metin: str) -> None:
    """Hata bildirimi; kendisi başarısız olursa yalnız log'a yazar."""
    try:
        _cagir(token, "sendMessage", {"chat_id": sahip_id, "text": metin}, {})
    except Exception as e:
        log.error("sahibe bildirim gönderilemedi: %s", e)
