"""Kullanım: python -m bioseeder.rasathane {evren,ilk-kurulum,sabah,haftalik,gun-ici} [--kuru] [--tarih YYYY-AA-GG]"""
import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from bioseeder.rasathane.ayar import CIKTI, VERI, ayar_oku
from bioseeder.rasathane.http import Istemci
from bioseeder.rasathane.isler import (
    Baglam, GercekKaynaklar, calistir, evren_isi, gun_ici_isi, haftalik_isi, ilk_kurulum_isi, sabah_isi,
)
from bioseeder.rasathane.grafik import yahoo_kapanislar
from bioseeder.rasathane.telegram import Telegram

# Türkiye 2016'dan beri sabit UTC+3 (yaz saati yok); Windows'ta tzdata gerektirmesin diye sabit.
ISTANBUL = timezone(timedelta(hours=3))
ISLER = ["evren", "ilk-kurulum", "sabah", "haftalik", "gun-ici"]


def istanbul_bugun(simdi: Optional[datetime] = None) -> date:
    return (simdi or datetime.now(timezone.utc)).astimezone(ISTANBUL).date()


def argumanlar(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m bioseeder.rasathane",
                                description="biOF → Rasathane Telegram kartları")
    p.add_argument("is_adi", choices=ISLER, help="çalıştırılacak iş")
    p.add_argument("--kuru", action="store_true", help="Telegram'a gönderme, kartları cikti/ altına yaz")
    p.add_argument("--tarih", type=date.fromisoformat, help="sabah işi için ABD işlem günü (YYYY-AA-GG)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    a = argumanlar(sys.argv[1:] if argv is None else argv)
    ayar = ayar_oku()
    bugun = istanbul_bugun()
    b = Baglam(kaynak=GercekKaynaklar(Istemci(sec_ua=ayar.sec_ua), VERI, bugun), telegram=Telegram(ayar),
               kuru=a.kuru or not ayar.gonderim_acik, bugun=bugun, veri=VERI, cikti=CIKTI,
               gonderim_acik=ayar.gonderim_acik, fiyat_cekici=yahoo_kapanislar)
    isler = {
        "evren": lambda: evren_isi(b),
        "ilk-kurulum": lambda: ilk_kurulum_isi(b),
        "sabah": lambda: sabah_isi(b, a.tarih),
        "haftalik": lambda: haftalik_isi(b),
        "gun-ici": lambda: gun_ici_isi(b),
    }
    return calistir(a.is_adi, isler[a.is_adi], b)


if __name__ == "__main__":
    sys.exit(main())
