"""ETF Radarı: liste, sinyaller, kopya ayıklama, kartlar ve akış (çevrimdışı)."""

import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from rasathane_ortak import kagit

from opsi.etf import calistir as etf_calistir
from opsi.etf import ekler, liste
from opsi.etf.cizim import (
    akis_ciz,
    hisseler_ciz,
    opsiyon_ciz,
    rejim_ciz,
    sinyal_grafigi,
    tema_haritasi_ciz,
    temalar_ciz,
    yeni_ciz,
    yeni_seyir_ciz,
)
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
    return Olcum(s, 20.0, 0.01, 2e6, 0.02, 0.1, g3a, 0.5)


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
        zincir_kaynagi=lambda _s, _b: {},
        hisse_kaynagi=lambda _s: [],
        varlik_kaynagi=lambda _s: {},
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


def test_asagi_yonlu_sinyaller() -> None:
    c = list(np.linspace(60, 50, 299)) + [48.0]
    df = _df(c)
    o = olc("X", df)
    assert o is not None
    assert "dip_52" in {s.tur for s in sinyaller("X", df, o)}
    c = list(np.linspace(80, 100, 280)) + [85.0]
    df = _df(c)
    o = olc("X", df)
    assert o is not None
    assert "sma200_asagi" in {s.tur for s in sinyaller("X", df, o)}


def test_rs_zirve_fiyat_zirvesinden_once() -> None:
    """ETF düz gidiyor, SPY düşüyor: oran zirvede, fiyat zirvenin altında."""
    n = 300
    c = np.r_[np.linspace(50, 60, 100), np.linspace(60, 55, n - 101), [56.0]]
    spy_c = np.r_[np.full(100, 400.0), np.linspace(400, 300, n - 101), [290.0]]
    df = _df(c)
    spy = pd.Series(spy_c, index=df.index)
    o = olc("X", df)
    assert o is not None
    rs = [s for s in sinyaller("X", df, o, spy) if s.tur == "rs_zirve"]
    assert rs and rs[0].seviye < 0


def test_tema_bul() -> None:
    assert ekler.tema_bul("Breakwave Tanker Shipping ETF") == "Denizcilik ve tanker"
    assert ekler.tema_bul("Global X Uranium ETF") == "Uranyum ve nükleer"
    assert ekler.tema_bul("Invesco Solar Energy ETF") == "Temiz enerji"
    assert ekler.tema_bul("Energy Select Sector SPDR") == "Petrol ve gaz"
    assert ekler.tema_bul("Netherlands Index Fund") is None


def test_opsiyon_ozeti() -> None:
    z = pd.DataFrame(
        {
            "tur": ["C", "C", "P"],
            "strike": [45.0, 50.0, 40.0],
            "vade": ["2026-11-20"] * 3,
            "volume": [4000, 1000, 500],
            "openInterest": [3000, 2000, 9000],
        }
    )
    r = ekler.opsiyon_ozeti("URA", z)
    assert len(r) == 1 and r[0].yon == "çağrı" and r[0].en_aktif == "45 C 20.11"
    assert r[0].oran == pytest.approx(1.0)


def test_fon_akisi_fiyat_etkisini_cikarir() -> None:
    gunler = [d.date().isoformat() for d in pd.bdate_range(end="2026-10-23", periods=6)]
    df = _df([10.0, 10, 10, 10, 10, 11.0], son="2026-10-23")
    v = pd.DataFrame({"tarih": gunler, "sembol": "X", "varlik": [100e6] * 5 + [120e6]})
    a = ekler.fon_akisi(v, {"X": df}, {"X": "X Fund"}, "2026-10-23")
    assert len(a) == 1 and a[0].akis == pytest.approx(10e6)


def test_yeni_seyir() -> None:
    df = _df([10.0] * 10 + [11.0] * 10, hacim=1e5, son="2026-10-23")
    df.iloc[-5:, df.columns.get_loc("Volume")] = 5e5
    kayit: dict[str, liste.Etf] = {
        "NEW": {"sembol": "NEW", "ad": "New Fund", "kaldirac": False, "ilk_gorulme": "2026-09-28"}
    }
    r = ekler.yeni_seyir(kayit, {"NEW": df}, "2026-10-26", "2026-10-19")
    assert len(r) == 1 and r[0].son_hacim > r[0].ilk_hacim


def test_ek_kartlar_cizilir() -> None:
    o = _olcum("URA", 0.3)
    tablolar = {s: _df(list(np.linspace(10, 12, 100))) for s in ("XLY", "XLP", "HYG", "IEF")}
    for k in (
        tema_haritasi_ciz(
            [ekler.TemaSatiri("Uranyum ve nükleer", 5, 0.02, 0.1, 0.3, "URA")], "2026-10-23"
        ),
        rejim_ciz(ekler.rejim(tablolar), "2026-10-23"),
        yeni_seyir_ciz(
            [ekler.YeniSeyir("NEW", "New Fund", "2026-10-01", 0.1, 1e6, 3e7)], "2026-10-26"
        ),
        opsiyon_ciz(
            [ekler.OpsiyonSatiri("URA", "çağrı", 12000, 8000, 1.5, 0.4, "45 C 20.11")],
            {},
            "2026-10-23",
            300,
        ),
        akis_ciz(
            [ekler.AkisSatiri("URA", "Uranium", 2.5e8, 0.05)],
            [ekler.AkisSatiri("XLE", "Energy", -1e9, -0.03)],
            "2026-10-23",
        ),
        hisseler_ciz(
            "URA",
            "Global X Uranium ETF",
            [("CCJ", "Cameco", 0.22, o, True), ("NXE", "NexGen", 0.06, None, False)],
            "2026-10-23",
        ),
    ):
        assert kagit.ciz(k, sayfa_basina=10)[0].png[:4] == b"\x89PNG"
