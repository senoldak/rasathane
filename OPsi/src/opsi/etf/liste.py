# src/opsi/etf/liste.py
"""ABD ETF listesi (Nasdaq ekran sorgusu) ve listeye ilk giriş günü; yeni ETF'ler buradan çıkar."""

import csv
import re
from pathlib import Path
from typing import Any, TypedDict

import requests

_URL = "https://api.nasdaq.com/api/screener/etf?download=true"
_BASLIK = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
_ZAMAN_ASIMI = 60
_EN_AZ = 1000  # bundan kısa liste eksik sayılır (kesinti); yeni ETF çıkarılmaz

# Kısa vadeli tahvil fonları ("Short-Term", "Ultra-Short Income") kaldıraçlı sayılmaz.
_TAHVIL = r"(?![-\s]*(term|duration|maturity|dated|income|treasury|bond|municipal|high))"
_KALDIRAC = re.compile(
    r"(\b\d+(\.\d+)?x\b|\bultrapro\b|\bultrashort\b|\bultra\b(?![-\s]*short[-\s]*(term|duration|maturity|income|treasury|bond|municipal))|\bbull\b|\bbear\b"
    r"|\binverse\b|\bleveraged\b|\bdaily target\b|\bshort\b" + _TAHVIL + ")",
    re.IGNORECASE,
)


class Etf(TypedDict):
    sembol: str
    ad: str
    kaldirac: bool
    ilk_gorulme: str  # ilk koşuda listede olanlar için boş


class Guncel(TypedDict):
    ad: str
    fiyat: float | None


def kaldiracli_mi(ad: str) -> bool:
    return bool(_KALDIRAC.search(ad))


def _fiyat(metin: str) -> float | None:
    try:
        return float(metin.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def ayristir(govde: dict[str, Any]) -> dict[str, Guncel]:
    satirlar = ((govde.get("data") or {}).get("data") or {}).get("rows") or []
    out: dict[str, Guncel] = {}
    for r in satirlar:
        sembol = str(r.get("symbol") or "").strip().upper().replace("/", "-")
        if sembol:
            out[sembol] = {
                "ad": str(r.get("companyName") or sembol).strip(),
                "fiyat": _fiyat(str(r.get("lastSalePrice") or "")),
            }
    return out


def nasdaq_listesi() -> dict[str, Guncel]:
    y = requests.get(_URL, headers=_BASLIK, timeout=_ZAMAN_ASIMI)
    y.raise_for_status()
    liste = ayristir(y.json())
    if len(liste) < _EN_AZ:
        raise RuntimeError(f"Nasdaq ETF listesi eksik: {len(liste)} satır")
    return liste


def oku(yol: Path) -> dict[str, Etf]:
    if not yol.exists():
        return {}
    with open(yol, encoding="utf-8", newline="") as f:
        return {
            r["sembol"]: {
                "sembol": r["sembol"],
                "ad": r["ad"],
                "kaldirac": r["kaldirac"] == "1",
                "ilk_gorulme": r["ilk_gorulme"],
            }
            for r in csv.DictReader(f)
        }


def yaz(kayit: dict[str, Etf], yol: Path) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["sembol", "ad", "kaldirac", "ilk_gorulme"])
        for s in sorted(kayit):
            e = kayit[s]
            w.writerow([s, e["ad"], "1" if e["kaldirac"] else "0", e["ilk_gorulme"]])


def birlestir(kayit: dict[str, Etf], guncel: dict[str, Guncel], bugun: str) -> dict[str, Etf]:
    """Listeye ilk kez girenleri bugünün tarihiyle ekler. Kayıt boşsa (ilk koşu) tarih boş kalır.

    Listeden düşenler kayıtta kalır: geri dönen bir ETF yeniden "yeni" sayılmaz.
    """
    ilk = not kayit
    out = dict(kayit)
    for s, g in guncel.items():
        if s not in out:
            out[s] = {
                "sembol": s,
                "ad": g["ad"],
                "kaldirac": kaldiracli_mi(g["ad"]),
                "ilk_gorulme": "" if ilk else bugun,
            }
    return out
