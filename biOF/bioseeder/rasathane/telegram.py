import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import httpx

from bioseeder.rasathane.ayar import Ayar
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi, sirayla_gonder


class TelegramHatasi(Exception):
    pass


class Telegram:
    def __init__(self, ayar: Ayar, transport: Optional[httpx.BaseTransport] = None,
                 uyku: Callable[[float], None] = time.sleep):
        self.ayar = ayar
        self.uyku = uyku
        self._istemci = httpx.Client(timeout=60.0, transport=transport)

    def _cagir(self, yontem: str, **kw: Any) -> Dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.ayar.bot_token}/{yontem}"
        for deneme in range(2):
            try:
                yanit = self._istemci.post(url, **kw)
                govde = yanit.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise TelegramHatasi(f"{yontem}: {exc}") from exc
            if govde.get("ok"):
                return govde
            bekle = (govde.get("parameters") or {}).get("retry_after")
            if govde.get("error_code") == 429 and bekle and deneme == 0:
                self.uyku(float(bekle))
                continue
            raise TelegramHatasi(f"{yontem}: {govde.get('description') or yanit.status_code}")
        raise TelegramHatasi(f"{yontem}: hız sınırı")

    def _hedef(self) -> Dict[str, str]:
        if not self.ayar.bot_token or not self.ayar.hedef_sohbet:
            raise TelegramHatasi("TELEGRAM_BOT_TOKEN ya da TELEGRAM_HEDEF tanımlı değil")
        alanlar = {"chat_id": self.ayar.hedef_sohbet}
        if self.ayar.hedef_konu is not None:
            alanlar["message_thread_id"] = str(self.ayar.hedef_konu)
        return alanlar

    def _istek(self, url: str, alanlar: Dict[str, str], dosyalar: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """rasathane_ortak.tek_gonderim için çok parçalı POST; (durum, JSON gövde) döner."""
        yanit = self._istemci.post(url, data=alanlar, files=dosyalar)
        try:
            return yanit.status_code, yanit.json()
        except ValueError:
            return yanit.status_code, {"ok": False, "description": yanit.text[:200]}

    def sirayla(self, gun: str, gidenler: Sequence[Giden], kayit: GonderimKaydi,
                sonrasi: Optional[Callable[[Giden, int], None]] = None) -> List[int]:
        """Kartları sırayla ayrı sendPhoto mesajları olarak gönderir; gönderilmiş kartları atlar."""
        alanlar = self._hedef()
        hedef = alanlar["chat_id"]
        if "message_thread_id" in alanlar:
            hedef += f":{alanlar['message_thread_id']}"
        return sirayla_gonder(self._istek, self.ayar.bot_token or "", hedef, gun, gidenler, kayit,
                              uyku=self.uyku, sonrasi=sonrasi)

    def sahibe(self, metin: str) -> None:
        if not self.ayar.bot_token or not self.ayar.sahip_id:
            return
        self._cagir("sendMessage", json={"chat_id": self.ayar.sahip_id, "text": metin[:4000]})
