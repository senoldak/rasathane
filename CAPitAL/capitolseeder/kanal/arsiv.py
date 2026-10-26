"""Depoda tutulan iki CSV: görülen beyanlar ve yapılan gönderimler."""
import csv
import datetime
from dataclasses import astuple, fields
from pathlib import Path

from capitolseeder.kanal.model import Beyan

ALANLAR = [f.name for f in fields(Beyan)]
GONDERIM_ALANLARI = ["tarih", "kartlar", "mesaj_id"]


def _beyana(satir: dict[str, str]) -> Beyan:
    return Beyan(
        id=satir["id"],
        ilk_gorulme=satir["ilk_gorulme"],
        uye=satir["uye"],
        parti=satir["parti"],
        eyalet=satir["eyalet"],
        meclis=satir["meclis"],
        ticker=satir["ticker"],
        varlik=satir["varlik"],
        varlik_turu=satir["varlik_turu"],
        islem=satir["islem"],
        tutar_alt=int(satir["tutar_alt"]),
        tutar_ust=int(satir["tutar_ust"]),
        tutar_etiket=satir["tutar_etiket"],
        islem_tarihi=datetime.date.fromisoformat(satir["islem_tarihi"]),
        beyan_tarihi=datetime.date.fromisoformat(satir["beyan_tarihi"]),
        gecikme=int(satir["gecikme"]),
        gec=satir["gec"] == "1",
        belge=satir["belge"],
    )


def beyanlari_oku(yol: Path) -> list[Beyan]:
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8", newline="") as f:
        return [_beyana(s) for s in csv.DictReader(f)]


def beyanlari_yaz(yol: Path, beyanlar: list[Beyan]) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".tmp")
    with gecici.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(ALANLAR)
        for b in beyanlar:
            w.writerow(["1" if v is True else "0" if v is False else v for v in astuple(b)])
    gecici.replace(yol)


def yenileri_ayir(kaynak: list[Beyan], arsiv: list[Beyan]) -> list[Beyan]:
    bilinen = {b.id for b in arsiv}
    return [b for b in kaynak if b.id not in bilinen]


def gonderildi_mi(yol: Path, tarih: datetime.date) -> bool:
    if not yol.exists():
        return False
    with yol.open(encoding="utf-8", newline="") as f:
        return any(s["tarih"] == tarih.isoformat() for s in csv.DictReader(f))


def gonderim_ekle(yol: Path, tarih: datetime.date, kartlar: list[str], mesaj_id: int) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yeni = not yol.exists()
    with yol.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if yeni:
            w.writerow(GONDERIM_ALANLARI)
        w.writerow([tarih.isoformat(), "|".join(kartlar), mesaj_id])
