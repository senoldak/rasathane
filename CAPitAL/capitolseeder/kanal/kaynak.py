"""Kadoa'nın derlediği beyan dosyasını indirir, doğrular ve Beyan'a çevirir."""
import datetime
import logging
import time
from typing import Any, Optional

import httpx

from capitolseeder.kanal.model import Beyan

logger = logging.getLogger("capitolseeder.kanal")

KAYNAK_URL = (
    "https://raw.githubusercontent.com/kadoa-org/congress-trading-monitor/main/public/data/trades.json"
)
GEREKLI_ALANLAR = ("id", "filer_name", "transaction_date", "filing_date", "transaction_type")
EKSIK_ORANI_SINIRI = 0.05
EN_ESKI_GUNCELLIK = 10  # gün


class VeriHatasi(Exception):
    pass


def indir(url: str = KAYNAK_URL, deneme: int = 3, istemci: Optional[httpx.Client] = None) -> list[dict]:
    istemci = istemci or httpx.Client(timeout=30.0, follow_redirects=True)
    son_hata: Any = None
    for i in range(deneme):
        try:
            yanit = istemci.get(url)
            yanit.raise_for_status()
            veri = yanit.json()
            if not isinstance(veri, list):
                raise VeriHatasi("Kaynak bir liste değil.")
            return veri
        except VeriHatasi:
            raise
        except Exception as e:  # ağ, HTTP, JSON
            son_hata = e
            logger.warning("Kaynak indirilemedi (%d/%d): %s", i + 1, deneme, e)
            if i + 1 < deneme:
                time.sleep(5)
    raise VeriHatasi(f"Kaynak {deneme} denemede indirilemedi: {son_hata}")


def _kongre(satirlar: list[dict]) -> list[dict]:
    return [s for s in satirlar if isinstance(s, dict) and s.get("branch") == "congress"]


def _tarih(deger: Any) -> datetime.date:
    return datetime.date.fromisoformat(str(deger)[:10])


def dogrula(satirlar: Any, bugun: datetime.date) -> None:
    if not isinstance(satirlar, list) or not satirlar:
        raise VeriHatasi("Kaynak boş ya da liste değil.")
    kongre = _kongre(satirlar)
    if not kongre:
        raise VeriHatasi("Kaynakta hiç Kongre beyanı yok.")
    eksik = sum(1 for s in kongre if any(not s.get(a) for a in GEREKLI_ALANLAR))
    if eksik / len(kongre) > EKSIK_ORANI_SINIRI:
        raise VeriHatasi(f"Kongre satırlarının {eksik}/{len(kongre)} tanesinde gerekli alan eksik.")
    tarihler = []
    for s in kongre:
        try:
            t = _tarih(s.get("filing_date"))
        except ValueError:
            continue  # tek bozuk satır günü durdurmaz; eksik oranı yukarıda sınırlı
        if t <= bugun + datetime.timedelta(days=1):  # gelecek tarihli yazım hatası bayat kaynağı gizlemesin
            tarihler.append(t)
    if not tarihler:
        raise VeriHatasi("Geçerli beyan tarihi yok.")
    en_yeni = max(tarihler)
    if (bugun - en_yeni).days > EN_ESKI_GUNCELLIK:
        raise VeriHatasi(f"Kaynak güncel değil: en yeni beyan {en_yeni}.")


def _sayi(deger: Any) -> int:
    try:
        return int(deger or 0)
    except (TypeError, ValueError):
        return 0


def kongre_beyanlari(satirlar: list[dict], ilk_gorulme: str) -> list[Beyan]:
    gorulen: set[str] = set()
    sonuc: list[Beyan] = []
    for s in _kongre(satirlar):
        kimlik = str(s.get("id") or "")
        if not kimlik or kimlik in gorulen or any(not s.get(a) for a in GEREKLI_ALANLAR):
            continue
        try:
            islem_tarihi = _tarih(s["transaction_date"])
            beyan_tarihi = _tarih(s["filing_date"])
        except ValueError:
            continue
        gorulen.add(kimlik)
        gecikme = s.get("days_to_file")
        sonuc.append(
            Beyan(
                id=kimlik,
                ilk_gorulme=ilk_gorulme,
                uye=str(s["filer_name"]).strip(),
                parti=(s.get("party") or "I").upper()[:1],
                eyalet=(s.get("state") or "").upper(),
                meclis="Senato" if (s.get("chamber") or "").lower() == "senate" else "Temsilciler",
                ticker=(s.get("ticker") or "").upper().strip(),
                varlik=(s.get("asset_name") or "").strip(),
                varlik_turu=(s.get("asset_type") or "").strip(),
                islem=str(s["transaction_type"]).strip(),
                tutar_alt=_sayi(s.get("amount_range_low")),
                tutar_ust=_sayi(s.get("amount_range_high")),
                tutar_etiket=(s.get("amount_range_label") or "").strip(),
                islem_tarihi=islem_tarihi,
                beyan_tarihi=beyan_tarihi,
                gecikme=_sayi(gecikme) if gecikme is not None else (beyan_tarihi - islem_tarihi).days,
                gec=bool(s.get("is_late")),
                belge=(s.get("doc_url") or "").strip(),
            )
        )
    return sonuc
