import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

AZAMI_OLAY = 5000


@dataclass
class Kayit:
    son_sabah_gunu: Optional[date] = None
    haftalik: List[date] = field(default_factory=list)
    gun_ici: Dict[str, int] = field(default_factory=dict)
    olaylar: List[str] = field(default_factory=list)
    edgar_imlec: Optional[str] = None

    @classmethod
    def oku(cls, yol: Path) -> "Kayit":
        if not yol.exists():
            return cls()
        v = json.loads(yol.read_text(encoding="utf-8"))
        return cls(
            son_sabah_gunu=date.fromisoformat(v["son_sabah_gunu"]) if v.get("son_sabah_gunu") else None,
            haftalik=[date.fromisoformat(g) for g in v.get("haftalik", [])],
            gun_ici=dict(v.get("gun_ici", {})),
            olaylar=list(v.get("olaylar", [])),
            edgar_imlec=v.get("edgar_imlec"),
        )

    def yaz(self, yol: Path) -> None:
        self.olaylar = self.olaylar[-AZAMI_OLAY:]
        veri = {
            "edgar_imlec": self.edgar_imlec,
            "gun_ici": dict(sorted(self.gun_ici.items())[-30:]),
            "haftalik": [g.isoformat() for g in self.haftalik[-60:]],
            "olaylar": self.olaylar,
            "son_sabah_gunu": self.son_sabah_gunu.isoformat() if self.son_sabah_gunu else None,
        }
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(json.dumps(veri, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def gonderildi_mi(self, kimlik: str) -> bool:
        return kimlik in self.olaylar

    def isaretle(self, kimlikler: Iterable[str]) -> None:
        self.olaylar.extend(k for k in kimlikler if k not in self.olaylar)

    def gun_ici_sayisi(self, gun_ist: date) -> int:
        return self.gun_ici.get(gun_ist.isoformat(), 0)

    def gun_ici_artir(self, gun_ist: date) -> None:
        self.gun_ici[gun_ist.isoformat()] = self.gun_ici_sayisi(gun_ist) + 1
