"""Telegram Bot API: ortak tek gönderim için HTTP isteği ve sahibe hata mesajı."""
import logging
import time
from typing import Callable, Dict, Tuple

import httpx

logger = logging.getLogger("inseeder.kanal.telegram")


class TelegramIstemcisi:
    def __init__(self, client: httpx.Client, token: str,
                 uyku: Callable[[float], None] = time.sleep):
        self.client = client
        self.token = token
        self.taban = f"https://api.telegram.org/bot{token}"
        self.uyku = uyku

    def istek(self, url: str, alanlar: Dict[str, str], dosyalar: Dict[str, Tuple]) -> Tuple[int, dict]:
        """rasathane_ortak.tek_gonderim için: çok parçalı POST, (durum, JSON gövde) döner."""
        yanit = self.client.post(url, data=alanlar, files=dosyalar)
        try:
            govde = yanit.json()
        except ValueError:
            govde = {"ok": False, "description": yanit.text[:200]}
        return yanit.status_code, govde

    def sahibe_yaz(self, sahip_id: str, metin: str) -> None:
        """Hata bildirimi; kendisi başarısız olursa yalnız loglanır."""
        try:
            yanit = self.client.post(f"{self.taban}/sendMessage",
                                     json={"chat_id": sahip_id, "text": metin[:4000]})
            if yanit.status_code != 200:
                logger.error(f"Sahibe hata mesajı gönderilemedi ({yanit.status_code}): {yanit.text[:200]}")
        except httpx.HTTPError as e:
            logger.error(f"Sahibe hata mesajı gönderilemedi: {e}")
