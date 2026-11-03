import datetime
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rasathane_emtia import raporlar
from rasathane_emtia.evren import TUM_SEMBOLLER
from rasathane_emtia.site_aktar import aktar
from rasathane_emtia.tarama import gram_altin, olc, oranlar, sinyaller

GUN = pd.bdate_range(end="2026-10-27", periods=600)
SIMDI = datetime.datetime(2026, 10, 27, 23, tzinfo=datetime.timezone.utc)
YASAK = re.compile(r"\b(al|sat|sinyal|öneri|fırsat)\b", re.IGNORECASE)


def _df(seri: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"Close": seri}, index=GUN[-len(seri) :])


def _yuruyus(tohum: int, son_adim: float = 0.0) -> np.ndarray:
    r = np.random.default_rng(tohum).normal(0, 0.01, len(GUN))
    r[-1] = son_adim
    return np.asarray(100 * np.exp(np.cumsum(r)))


def _calis(
    kok: Path, ozel: dict[str, float] | None = None, rapor: dict[str, Any] | None = None
) -> list[Path]:
    ozel = ozel or {}
    tablolar = {s: _df(_yuruyus(i, ozel.get(s, 0.0))) for i, s in enumerate(TUM_SEMBOLLER)}
    olcumler = {}
    bulunan = []
    for s, df in tablolar.items():
        o = olc(s, df)
        assert o is not None
        olcumler[s] = o
        if s not in ("TRY=X", "DX-Y.NYB"):
            bulunan.extend(sinyaller(s, df, o))
    gram = gram_altin(tablolar)
    assert gram is not None
    return aktar(
        kok,
        SIMDI,
        "2026-10-27",
        tablolar,
        olcumler,
        gram,
        olc("gram", pd.DataFrame({"Close": gram})),
        oranlar(tablolar),
        bulunan,
        rapor or {},
    )


def _oku(yol: Path) -> Any:
    return json.loads(yol.read_text("utf-8"))


def test_aktar_sayfa_ve_seriler(tmp_path: Path) -> None:
    _calis(tmp_path)
    e = tmp_path / "emtia"
    for ad in ("pano", "hareketler"):
        assert (e / f"{ad}.json").exists()
    pano = _oku(e / "pano.json")
    assert len(pano["satirlar"]) == 23
    assert pano["suzgecler"] == ["grup"]
    gunluk = _oku(e / "seri" / "GC=F.json")
    assert len(gunluk["tarihler"]) == 252
    assert {"kapanis", "ema144", "ema233", "ema377", "rsi14"} <= set(gunluk["sutunlar"])
    haftalik = _oku(e / "seri" / "GC=F-hafta.json")
    assert len(haftalik["tarihler"]) <= 104
    assert {"kapanis", "ema144", "ema233", "rsi14"} <= set(haftalik["sutunlar"])
    assert len(_oku(e / "seri" / "gram.json")["tarihler"]) == 252


def test_rapor_yoksa_stok_ve_fon_yazilmaz(tmp_path: Path) -> None:
    onceki = tmp_path / "emtia" / "stoklar.json"
    onceki.parent.mkdir(parents=True)
    onceki.write_text("{}", "utf-8")
    _calis(tmp_path)
    assert onceki.read_text("utf-8") == "{}"
    assert not (tmp_path / "emtia" / "fonlar.json").exists()


def test_hareket_isaretli(tmp_path: Path) -> None:
    _calis(tmp_path, {"GC=F": 0.08})
    e = tmp_path / "emtia"
    satirlar = _oku(e / "hareketler.json")["satirlar"]
    assert any(s["seri"] == "GC=F" for s in satirlar)
    isaretler = _oku(e / "seri" / "GC=F.json")["isaretler"]
    assert isaretler and isaretler[0][0] == "2026-10-27"


def test_stok_ve_fon_sayfalari(tmp_path: Path) -> None:
    stok = raporlar.Stok(
        raporlar.DOGALGAZ,
        "2026-10-16",
        3800.0,
        50.0,
        3700.0,
        (("2026-10-16", 3800.0), ("2026-10-09", 3750.0)),
    )
    poz = raporlar.Pozisyon(
        "GC=F", "2026-10-20", 900, 10, 0.97, 5000, (("2026-10-20", 900), ("2026-10-13", 890))
    )
    _calis(tmp_path, rapor={"eia_gaz": [stok], "cot": [poz]})
    e = tmp_path / "emtia"
    assert len(_oku(e / "stoklar.json")["satirlar"]) == 1
    assert len(_oku(e / "seri" / "eia-NW2-EPG0-SWO-R48-BCF.json")["noktalar"]) == 2
    assert _oku(e / "fonlar.json")["satirlar"][0]["seri"] == "cftc-GC=F"
    assert len(_oku(e / "seri" / "cftc-GC=F.json")["noktalar"]) == 2


def test_metinde_yasak_sozcuk_yok(tmp_path: Path) -> None:
    stok = raporlar.Stok(
        raporlar.PETROL[1], "2026-10-16", 3.0, 1.0, 2.0, (("2026-10-16", 3.0), ("2026-10-09", 2.0))
    )
    poz = raporlar.Pozisyon(
        "CL=F", "2026-10-20", 900, 10, 0.97, 5000, (("2026-10-20", 900), ("2026-10-13", 890))
    )
    yollar = _calis(tmp_path, {"GC=F": 0.08, "CL=F": -0.09}, {"eia_petrol": [stok], "cot": [poz]})
    assert yollar
    dosyalar = list((tmp_path / "emtia").rglob("*.json"))
    assert dosyalar
    for yol in dosyalar:
        bulunan = YASAK.findall(yol.read_text("utf-8"))
        assert not bulunan, (yol, bulunan)
