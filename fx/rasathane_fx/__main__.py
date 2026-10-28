"""python -m rasathane_fx [--kuru] [--tarih YYYY-AA-GG]"""

import argparse
import logging

from .calistir import calistir


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="rasathane_fx")
    p.add_argument("--kuru", action="store_true", help="kartları üret, gönderme")
    p.add_argument("--tarih", default=None, help="YYYY-AA-GG (yalnız son seans)")
    a = p.parse_args()
    print(calistir(kuru=a.kuru, tarih=a.tarih or None))


if __name__ == "__main__":
    main()
