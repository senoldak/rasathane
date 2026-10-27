"""ETF Radarı: liste, sinyaller, kopya ayıklama, kartlar ve akış (çevrimdışı)."""

import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from rasathane_ortak import kagit

from opsi.etf import calistir as etf_calistir
from opsi.etf import liste
from opsi.etf.cizim import sinyal_grafigi, temalar_ciz, yeni_ciz
from opsi.etf.tarama import Olcum, kopyalari_ayikla, olc, sinyaller


def _df(
    kapanis: list[float] | np.ndarray, hacim: float = 1e6, son: str = "2026-10-23"
) -> pd.DataFrame:
    gunler = pd.bdate_range(end=son, periods=len(kapanis))
    c = np.asarray(kapanis, dtype=float)
    return pd.DataFrame(
        {"Close": c, "High": c * 1.01, "Low": c * 0.99, "Volume": hacim}, index=gunler
    )


@pytest.mark.parametrize(
    ("ad", "beklenen"),
    [
        ("ProShares UltraPro QQQ", True),
        ("Direxion Daily Semiconductor Bull 3X Shares", True),
        ("ProShares Short S&P500", True),
        ("ProShares UltraShort Euro", True),
        ("JPMorgan Ultra-Short Income ETF", False),
        ("SPDR Bloomberg Short Term Treasury ETF", False),
        ("Breakwave Dry Bulk Shipping ETF", False),
        ("Invesco BulletShares 2027 Corporate Bond ETF", False),
    ],
)
def test_kaldirac(ad: str, beklenen: bool) -> None:
    assert liste.kaldiracli_mi(ad) is beklenen


def test_ayristir_ve_birlestir(tmp_path: Path) -> None:
    govde = {
        "data": {
            "data": {
                "rows": [
                    {
                        "symbol": "BWET",
                        "companyName": "Breakwave Tanker Shipping ETF",
                        "lastSalePrice": "$21.50",
                    },
                    {"symbol": "BRK/B", "companyName": "x", "lastSalePrice": "n/a"},
                ]
            }
        }
    }
    g = liste.ayristir(govde)
    assert g["BWET"]["fiyat"] == 21.5 and g["BRK-B"]["fiyat"] is None
    ilk = liste.birlestir({}, g, "2026-10-23")
    assert all(e["ilk_gorulme"] == "" for e in ilk.values())  # ilk koşuda hepsi "yeni" sayılmaz
    yol = tmp_path / "l.csv"
    liste.yaz(ilk, yol)
    g["URNM"] = {"ad": "Sprott Uranium Miners ETF", "fiyat": 50.0}
    ikinci = liste.birlestir(liste.oku(yol), g, "2026-10-26")
    assert ikinci["URNM"]["ilk_gorulme"] == "2026-10-26"
    assert ikinci["BWET"]["ilk_gorulme"] == ""


def test_zirve_ve_hacim() -> None:
    c = list(np.linspace(50, 60, 299)) + [62.0]
    df = _df(c)
    df.iloc[-1, df.columns.get_loc("Volume")] = 5e6
    o = olc("X", df)
    assert o is not None
    turler = {s.tur for s in sinyaller("X", df, o)}
    assert {"zirve_52", "hacim"} <= turler


def test_zirve_ikinci_gun_tekrarlanmaz() -> None:
    c = list(np.linspace(50, 60, 298)) + [62.0, 63.0]
    df = _df(c)
    o = olc("X", df)
    assert o is not None
    assert "zirve_52" not in {s.tur for s in sinyaller("X", df, o)}


def test_sma200_yukari() -> None:
    c = list(np.linspace(100, 80, 280)) + [95.0]
    df = _df(c)
    o = olc("X", df)
    assert o is not None
    assert "sma200_yukari" in {s.tur for s in sinyaller("X", df, o)}


def test_likit_olmayan_olculmez() -> None:
    assert olc("X", _df([10.0] * 30, hacim=1000)) is None


def test_kopyalar_ayiklanir() -> None:
    rng = np.random.default_rng(1)
    a = 100 * np.cumprod(1 + rng.normal(0, 0.01, 200))
    b = a * 1.0001
    c = 100 * np.cumprod(1 + rng.normal(0, 0.01, 200))
    veri = {"SPY": _df(a), "VOO": _df(b), "BWET": _df(c)}
    assert kopyalari_ayikla(["SPY", "VOO", "BWET"], veri) == ["SPY", "BWET"]


def _olcum(s: str, g3a: float) -> Olcum:
    return Olcum(s, 20.0, 0.01, 2e6, 0.1, g3a, 0.5)


def test_kartlar_cizilir() -> None:
    e: liste.Etf = {
        "sembol": "BWET",
        "ad": "Breakwave Tanker Shipping ETF",
        "kaldirac": False,
        "ilk_gorulme": "2026-10-20",
    }
    for k in (
        yeni_ciz([e], {"BWET": {"ad": e["ad"], "fiyat": 21.5}}, "2026-10-26", "2026-10-19"),
        temalar_ciz(
            [_olcum("BWET", 1.2), _olcum("URA", 0.4)],
            {"BWET": "Tanker"},
            _olcum("SPY", 0.05),
            "2026-10-23",
            900,
        ),
    ):
        assert kagit.ciz(k, sayfa_basina=10)[0].png[:4] == b"\x89PNG"
    c = list(np.linspace(50, 60, 299)) + [62.0]
    df = _df(c)
    o = olc("BWET", df)
    assert o is not None
    s = next(x for x in sinyaller("BWET", df, o) if x.tur == "zirve_52")
    assert kagit.grafik_ciz(sinyal_grafigi(s, e["ad"], False, df, "2026-10-23"))[:4] == b"\x89PNG"


def test_akis_kuru(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cuma, ilk koşu: temalar ve sinyal kartları çıkar; kuru koşu kayıt yazmaz."""
    gunler = [d.date().isoformat() for d in pd.bdate_range(end="2026-10-23", periods=20)]
    monkeypatch.setattr(etf_calistir, "_spy_gunleri", lambda: gunler)
    rng = np.random.default_rng(2)
    tablolar = {
        f"E{i}": _df(list(100 * np.cumprod(1 + rng.normal(0.001 * i, 0.01, 299))) + [1e4])
        for i in range(10)
    }
    tablolar["SPY"] = _df(list(np.linspace(400, 450, 300)))
    guncel: dict[str, liste.Guncel] = {
        s: {"ad": f"{s} Fund", "fiyat": 10.0} for s in tablolar if s != "SPY"
    }
    sonuc = etf_calistir.calistir(
        kuru=True,
        tarih="2026-10-23",
        cikti=tmp_path / "c",
        veri=tmp_path / "v",
        indir=lambda _s: tablolar,
        liste_kaynagi=lambda: guncel,
    )
    assert sonuc["durum"] == "kuru" and sonuc["sinyal_sayisi"] >= 1
    assert len(list((tmp_path / "c").glob("*.png"))) == sonuc["kart_sayisi"]
    assert not (tmp_path / "v").exists()


def test_susturma(tmp_path: Path) -> None:
    yol = tmp_path / "s.csv"
    yol.write_text(
        "tarih,tur,sembol\n2026-10-20,zirve_52,BWET\n2026-09-01,altin,URA\n", encoding="utf-8"
    )
    gunler = [d.date().isoformat() for d in pd.bdate_range(end="2026-10-23", periods=40)]
    s = etf_calistir._susturulanlar(yol, "2026-10-23", gunler)
    assert s == {("zirve_52", "BWET")}
    assert datetime.date(2026, 10, 23).weekday() == 4
