from __future__ import annotations

from datetime import date
from pathlib import Path

from rasathane_bist.calistir import calistir, son_bulten
from rasathane_bist.indir import Indirici

VERI = Path(__file__).parent / "veri"
BULTEN_GUNU = date(2026, 10, 23)


def _sahte(istekler: list[str]) -> Indirici:
    """Yalnız 23 Ekim bülteni var; diğer günler 404."""
    bayt = (VERI / "viop_ornek.csv").read_bytes()

    def indir(url: str) -> tuple[int, bytes]:
        istekler.append(url)
        return (200, bayt) if url.endswith("viop_20261023.csv") else (404, b"")

    return indir


def test_son_bulten_hafta_sonunu_atlar() -> None:
    istekler: list[str] = []
    sonuc = son_bulten(date(2026, 10, 25), _sahte(istekler))
    assert sonuc is not None
    gun, satirlar = sonuc
    assert gun == BULTEN_GUNU and len(satirlar) == 13
    assert istekler[0] == "https://borsaistanbul.com/data/vadeli/viop_20261025.csv"
    assert istekler[-1].endswith("viop_20261023.csv")


def test_son_bulten_yoksa_none() -> None:
    assert son_bulten(date(2026, 10, 25), lambda url: (404, b""), geri=3) is None


def test_calistir_site_yazar(tmp_path: Path) -> None:
    yollar = calistir(
        tmp_path,
        bugun=date(2026, 10, 25),
        indir=_sahte([]),
        endeks=False,
    )
    assert yollar is not None
    assert (tmp_path / "viop" / "vadeli.json").is_file()
    assert not (tmp_path / "viop" / "opsiyon.json").exists()


def test_calistir_bulten_yoksa_none_ve_dosya_yazmaz(tmp_path: Path) -> None:
    yollar = calistir(
        tmp_path,
        bugun=date(2026, 10, 25),
        indir=lambda url: (404, b""),
        endeks=False,
    )
    assert yollar is None
    assert not (tmp_path / "viop").exists()
