from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from rasathane_bist.yahoo import kapanis_serisi, kapanislar


def _sahte(veri: dict[str, dict[str, float]], cagrilar: list[dict[str, Any]] | None = None) -> Any:
    """yfinance.download gibi: (semboller, start=, end=, auto_adjust=, progress=) -> DataFrame."""

    def indir(semboller: Any, **kw: Any) -> Any:
        if cagrilar is not None:
            cagrilar.append({"semboller": semboller, **kw})
        sutunlar = {}
        for s in semboller if isinstance(semboller, list) else [semboller]:
            seri = veri.get(s, {})
            sutunlar[("Close", s)] = pd.Series(
                list(seri.values()), index=pd.to_datetime(list(seri.keys())), dtype=float
            )
        if not sutunlar:
            return pd.DataFrame()
        df = pd.DataFrame(sutunlar)
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        return df

    return indir


VERI = {
    "THYAO.IS": {"2026-10-22": 258.0, "2026-10-23": 260.4},
    "BZ=F": {"2026-10-20": 70.0},
}


def test_kapanislar_eksik_sembol_yok() -> None:
    assert kapanislar(["THYAO.IS", "YOK"], date(2026, 10, 23), indir=_sahte(VERI)) == {
        "THYAO.IS": 260.4
    }


def test_kapanislar_gunden_sonrasini_almaz_ve_geriye_bakar() -> None:
    sonuc = kapanislar(["THYAO.IS", "BZ=F"], date(2026, 10, 22), indir=_sahte(VERI))
    assert sonuc == {"THYAO.IS": 258.0, "BZ=F": 70.0}


def test_kapanislar_bes_gunden_eski_yok() -> None:
    assert kapanislar(["BZ=F"], date(2026, 10, 26), indir=_sahte(VERI)) == {}


def test_kapanislar_cagri_bicimi() -> None:
    cagrilar: list[dict[str, Any]] = []
    kapanislar(["THYAO.IS"], date(2026, 10, 23), indir=_sahte(VERI, cagrilar))
    assert cagrilar[0]["auto_adjust"] is True
    assert cagrilar[0]["progress"] is False


def test_kapanis_serisi() -> None:
    seri = kapanis_serisi("THYAO.IS", date(2026, 10, 23), 30, indir=_sahte(VERI))
    assert seri == [(date(2026, 10, 22), 258.0), (date(2026, 10, 23), 260.4)]


def test_kapanis_serisi_bos() -> None:
    assert kapanis_serisi("YOK", date(2026, 10, 23), indir=_sahte(VERI)) == []
