# src/opsi/kanal/gecmis.py
"""Kanalın kalıcı durumu: günlük IV geçmişi (CSV) ve gönderilen tarihler (JSON).

Dosyalar depoda takip edilir (`kanal_veri/`); Actions koşusu commit edip geri yükler.
"""

import csv
import json
from pathlib import Path
from typing import TypedDict

GECMIS_YOLU = Path("kanal_veri/iv_gecmisi.csv")
GONDERILEN_YOLU = Path("kanal_veri/gonderilenler.json")
_RANK_GUN = 252


class Kayit(TypedDict):
    tarih: str
    sembol: str
    kapanis: float
    iv30: float | None
    skew25: float | None
    atm_iv: float | None
    bilanco_gun: int | None


_ALANLAR = ["tarih", "sembol", "kapanis", "iv30", "skew25", "atm_iv", "bilanco_gun"]


def _f(s: str) -> float | None:
    return float(s) if s != "" else None


def _i(s: str) -> int | None:
    return int(s) if s != "" else None


def oku(yol: Path = GECMIS_YOLU) -> list[Kayit]:
    if not yol.exists():
        return []
    with yol.open(newline="", encoding="utf-8") as f:
        return [
            {
                "tarih": r["tarih"],
                "sembol": r["sembol"],
                "kapanis": float(r["kapanis"]),
                "iv30": _f(r["iv30"]),
                "skew25": _f(r["skew25"]),
                "atm_iv": _f(r["atm_iv"]),
                "bilanco_gun": _i(r["bilanco_gun"]),
            }
            for r in csv.DictReader(f)
        ]


def gun_yaz(kayitlar: list[Kayit], yol: Path = GECMIS_YOLU) -> None:
    """Kayıtların tarihlerine ait eski satırları silip yenilerini yazar."""
    tarihler = {k["tarih"] for k in kayitlar}
    tum = [k for k in oku(yol) if k["tarih"] not in tarihler] + list(kayitlar)
    tum.sort(key=lambda k: (k["tarih"], k["sembol"]))
    yol.parent.mkdir(parents=True, exist_ok=True)
    with yol.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_ALANLAR)
        w.writeheader()
        for k in tum:
            w.writerow({a: ("" if k[a] is None else k[a]) for a in _ALANLAR})  # type: ignore[literal-required]


def onceki_gun(kayitlar: list[Kayit], tarih: str) -> str | None:
    once = [k["tarih"] for k in kayitlar if k["tarih"] < tarih]
    return max(once) if once else None


def iv_seri(kayitlar: list[Kayit], sembol: str, son_tarih: str) -> list[float]:
    s = sorted(
        (k["tarih"], k["iv30"])
        for k in kayitlar
        if k["sembol"] == sembol and k["tarih"] <= son_tarih and k["iv30"] is not None
    )
    return [v for _, v in s if v is not None]


def iv_konum(seri: list[float], ilk_tarih: str) -> tuple[float, str]:
    """Son değerin konumu: 252 gün varsa IV Rank, yoksa birikmiş geçmişte yüzdelik."""
    if not seri:
        return 0.5, ""
    bugun = seri[-1]
    if len(seri) >= _RANK_GUN:
        son = seri[-_RANK_GUN:]
        lo, hi = min(son), max(son)
        v = 0.5 if hi == lo else (bugun - lo) / (hi - lo)
        return v, "IV Rank (1 yıl)"
    _, ay, gun = ilk_tarih.split("-")
    return sum(1 for x in seri if x <= bugun) / len(seri), f"IV yüzd. ({gun}.{ay}'dan beri)"


def _gonderilenler(yol: Path) -> list[str]:
    if not yol.exists():
        return []
    veri = json.loads(yol.read_text(encoding="utf-8"))
    return list(veri.get("tarihler", []))


def gonderildi_mi(tarih: str, yol: Path = GONDERILEN_YOLU) -> bool:
    return tarih in _gonderilenler(yol)


def gonderildi_isaretle(tarih: str, yol: Path = GONDERILEN_YOLU) -> None:
    t = _gonderilenler(yol)
    if tarih not in t:
        t.append(tarih)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"tarihler": sorted(t)}, indent=1) + "\n", encoding="utf-8")
