from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from rasathane_bist.site_aktar import aktar
from rasathane_bist.viop import ViopSatiri, viop_bulteni_oku

VERI = Path(__file__).parent / "veri"
SIMDI = datetime(2026, 10, 23, 18, tzinfo=timezone.utc)


def _bulten() -> tuple[date, list[ViopSatiri]]:
    return viop_bulteni_oku((VERI / "viop_ornek.csv").read_bytes())


def _oku(yol: Path) -> Any:
    return json.loads(yol.read_text("utf-8"))


def test_yalniz_vadeli_sayfasi_yazilir(tmp_path: Path) -> None:
    gun, satirlar = _bulten()
    yollar = aktar(tmp_path, gun, satirlar, SIMDI)
    assert [y.name for y in yollar] == ["vadeli.json"]
    assert not (tmp_path / "viop" / "opsiyon.json").exists()
    vadeli = _oku(tmp_path / "viop" / "vadeli.json")
    assert vadeli["sema"] == 1 and vadeli["bolum"] == "viop"
    assert vadeli["grafik"] == "yok"
    assert "23.10.2026" in vadeli["aciklama"]
    assert len(vadeli["satirlar"]) == 6  # 13 satırın 6'sı F_ (vadeli)


def test_vadeli_hacme_gore_azalan_ve_anahtarlar_sutunlarla_ayni(tmp_path: Path) -> None:
    gun, satirlar = _bulten()
    aktar(tmp_path, gun, satirlar, SIMDI)
    veri = _oku(tmp_path / "viop" / "vadeli.json")
    hacimler = [r["hacim"] for r in veri["satirlar"]]
    assert hacimler == sorted(hacimler, reverse=True)
    beklenen = {s["anahtar"] for s in veri["sutunlar"]}
    for satir in veri["satirlar"]:
        assert set(satir) == beklenen
