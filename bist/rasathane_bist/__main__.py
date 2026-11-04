"""python -m rasathane_bist [--tarih YYYY-AA-GG] [--site DIZIN] [--faiz ORAN]"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from .calistir import GECMIS_YOLU, calistir


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="rasathane_bist")
    p.add_argument("--tarih", default=None, help="YYYY-AA-GG (boş: bugün, geriye doğru bakar)")
    p.add_argument("--site", type=Path, required=True, help="site JSON'larını bu klasöre yaz")
    p.add_argument(
        "--faiz",
        type=float,
        default=None,
        help="risksiz faiz, ondalık (TLREF %%35,8 ise 0.358); verilmezse etkin kaldıraç yok",
    )
    a = p.parse_args()
    bugun = date.fromisoformat(a.tarih) if a.tarih else None
    sonuc = calistir(a.site, bugun=bugun, faiz=a.faiz, gecmis_yolu=GECMIS_YOLU)
    if sonuc is None:
        sys.exit(1)
    print(f"{len(sonuc)} sayfa yazıldı: {a.site}")


if __name__ == "__main__":
    main()
