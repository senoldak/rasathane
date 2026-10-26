"""Depoda tutulan kanal kaydı: beyanlar.csv ve gonderilenler.json."""
import csv
import json
from dataclasses import asdict, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple

from inseeder.kanal.model import Beyan

ALANLAR = [f.name for f in fields(Beyan)]
SAKLAMA_GUN = 35


def _beyan_oku(satir: Dict[str, str]) -> Beyan:
    return Beyan(
        dosyalama_gunu=date.fromisoformat(satir["dosyalama_gunu"]),
        accession_no=satir["accession_no"],
        sembol=satir["sembol"],
        sirket=satir["sirket"],
        kisi=satir["kisi"],
        unvan=satir["unvan"],
        kod=satir["kod"],
        adet=float(satir["adet"]),
        ort_fiyat=float(satir["ort_fiyat"]),
        tutar=float(satir["tutar"]),
        sonraki_pay=float(satir["sonraki_pay"]) if satir["sonraki_pay"] else None,
        plan_10b5_1=satir["plan_10b5_1"] == "True",
        sec_url=satir["sec_url"],
    )


class Kayit:
    def __init__(self, dizin: Path):
        self.dizin = Path(dizin)
        self._beyanlar: Dict[Tuple[str, str], Beyan] = {}
        self._durum: Dict[str, Set[date]] = {"islenen": set(), "gunluk": set(), "haftalik": set()}
        csv_yolu = self.dizin / "beyanlar.csv"
        if csv_yolu.exists():
            with open(csv_yolu, encoding="utf-8", newline="") as f:
                self.ekle([_beyan_oku(s) for s in csv.DictReader(f)])
        json_yolu = self.dizin / "gonderilenler.json"
        if json_yolu.exists():
            veri = json.loads(json_yolu.read_text(encoding="utf-8"))
            for anahtar in self._durum:
                self._durum[anahtar] = {date.fromisoformat(g) for g in veri.get(anahtar, [])}

    def beyanlar(self) -> List[Beyan]:
        return list(self._beyanlar.values())

    def ekle(self, yeni: List[Beyan]) -> None:
        for b in yeni:
            self._beyanlar.setdefault((b.accession_no, b.kod), b)

    def buda(self, bugun: date, gun: int = SAKLAMA_GUN) -> None:
        sinir = bugun - timedelta(days=gun)
        self._beyanlar = {k: b for k, b in self._beyanlar.items() if b.dosyalama_gunu >= sinir}
        self._durum["islenen"] = {g for g in self._durum["islenen"] if g >= sinir}

    def islenen_gunler(self) -> Set[date]:
        return set(self._durum["islenen"])

    def islendi(self, g: date) -> None:
        self._durum["islenen"].add(g)

    def gunluk_gonderildi_mi(self, g: date) -> bool:
        return g in self._durum["gunluk"]

    def gunluk_gonderildi(self, g: date) -> None:
        self._durum["gunluk"].add(g)

    def haftalik_gonderildi_mi(self, pazartesi: date) -> bool:
        return pazartesi in self._durum["haftalik"]

    def haftalik_gonderildi(self, pazartesi: date) -> None:
        self._durum["haftalik"].add(pazartesi)

    def kaydet(self) -> None:
        self.dizin.mkdir(parents=True, exist_ok=True)
        satirlar = sorted(self._beyanlar.values(), key=lambda b: (b.dosyalama_gunu, b.accession_no, b.kod))
        with open(self.dizin / "beyanlar.csv", "w", encoding="utf-8", newline="") as f:
            yazici = csv.DictWriter(f, fieldnames=ALANLAR, lineterminator="\n")
            yazici.writeheader()
            for b in satirlar:
                d = asdict(b)
                d["dosyalama_gunu"] = b.dosyalama_gunu.isoformat()
                d["sonraki_pay"] = "" if b.sonraki_pay is None else b.sonraki_pay
                yazici.writerow(d)
        durum = {k: sorted(g.isoformat() for g in v) for k, v in self._durum.items()}
        (self.dizin / "gonderilenler.json").write_text(
            json.dumps(durum, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
