import json as _json
import time
from typing import Any, Callable, Dict, Optional

import httpx

_YENIDEN = (403, 429, 500, 502, 503, 504)


class KaynakHatasi(Exception):
    def __init__(self, mesaj: str, durum: Optional[int] = None):
        super().__init__(mesaj)
        self.durum = durum


class Istemci:
    """Senkron, hız sınırlı HTTP istemcisi. SEC'e yalnız beyanlı User-Agent ile gider."""

    def __init__(
        self,
        hz: float = 5.0,
        deneme: int = 4,
        zaman_asimi: float = 30.0,
        uyku: Callable[[float], None] = time.sleep,
        saat: Callable[[], float] = time.monotonic,
        transport: Optional[httpx.BaseTransport] = None,
        sec_ua: Optional[str] = None,
    ):
        self.sec_ua = sec_ua
        self.aralik = 1.0 / hz
        self.deneme = deneme
        self.uyku = uyku
        self.saat = saat
        self._son: Optional[float] = None
        self._istemci = httpx.Client(timeout=zaman_asimi, transport=transport, follow_redirects=True)

    def _bekle(self) -> None:
        if self._son is not None:
            kalan = self._son + self.aralik - self.saat()
            if kalan > 0:
                self.uyku(kalan)
        self._son = self.saat()

    def _istek(self, url: str, params: Optional[Dict[str, Any]], sec: bool) -> httpx.Response:
        if sec and not self.sec_ua:
            raise KaynakHatasi("SEC_ILETISIM tanımlı değil; SEC isteği için iletişim e-postası gerekli")
        basliklar = (
            {"User-Agent": self.sec_ua, "Accept-Encoding": "gzip, deflate"}
            if sec
            else {"User-Agent": "biOF Rasathane"}
        )
        son_hata = ""
        for deneme in range(self.deneme + 1):
            self._bekle()
            try:
                yanit = self._istemci.get(url, params=params, headers=basliklar)
            except httpx.RequestError as exc:
                son_hata = f"ağ hatası: {exc}"
            else:
                if yanit.status_code == 200:
                    return yanit
                if yanit.status_code == 404:
                    raise KaynakHatasi(f"Bulunamadı (404): {url}", 404)
                if yanit.status_code not in _YENIDEN:
                    raise KaynakHatasi(f"HTTP {yanit.status_code}: {url}", yanit.status_code)
                son_hata = f"HTTP {yanit.status_code}"
                if deneme < self.deneme:
                    # SEC sınır aşımında IP'yi ~10 dk engelliyor; kısa beklemek işe yaramaz.
                    if "Request Rate Threshold" in yanit.text:
                        self.uyku(60.0 * (deneme + 1))
                        continue
                    self.uyku(2.0 ** deneme)
                    continue
            if deneme < self.deneme:
                self.uyku(2.0 ** deneme)
        raise KaynakHatasi(f"{url} okunamadı ({self.deneme + 1} deneme): {son_hata}")

    def metin(self, url: str, params: Optional[Dict[str, Any]] = None, sec: bool = False) -> str:
        return self._istek(url, params, sec).text

    def json(self, url: str, params: Optional[Dict[str, Any]] = None, sec: bool = False) -> Any:
        yanit = self._istek(url, params, sec)
        try:
            return yanit.json()
        except _json.JSONDecodeError as exc:
            raise KaynakHatasi(f"Geçersiz JSON: {url}") from exc
