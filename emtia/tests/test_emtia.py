import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rasathane_emtia import calistir as c
from rasathane_emtia import raporlar
from rasathane_emtia.evren import TUM_SEMBOLLER
from rasathane_emtia.tarama import gram_altin, olc, oranlar, rekor_mu, sinyaller

GUN = pd.bdate_range(end="2026-10-27", periods=600)


def _df(seri: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"Close": seri}, index=GUN[-len(seri) :])


def _yuruyus(tohum: int, son_adim: float = 0.0) -> np.ndarray:
    r = np.random.default_rng(tohum).normal(0, 0.01, len(GUN))
    r[-1] = son_adim
    return np.asarray(100 * np.exp(np.cumsum(r)))


def test_sert_hareket_ve_zirve() -> None:
    seri = _yuruyus(1)
    seri[-1] = seri[:-1].max() * 1.08
    df = _df(seri)
    o = olc("GC=F", df)
    assert o is not None and o.z is not None and o.z > 2.5
    turler = {s.tur for s in sinyaller("GC=F", df, o)}
    assert turler == {"yukselis", "zirve_52"}


def test_sakin_gun_sinyalsiz() -> None:
    df = _df(_yuruyus(2, 0.001))
    o = olc("GC=F", df)
    assert o is not None
    assert [s.tur for s in sinyaller("GC=F", df, o)] in ([], ["zirve_52"], ["dip_52"])
    assert not any(s.tur in ("yukselis", "dusus") for s in sinyaller("GC=F", df, o))


def test_oran_yuzdelik_ve_gram() -> None:
    altin = np.linspace(100, 200, len(GUN))
    gumus = np.full(len(GUN), 2.0)
    t = {"GC=F": _df(altin), "SI=F": _df(gumus), "TRY=X": _df(np.full(len(GUN), 40.0))}
    (r,) = [x for x in oranlar(t) if x.oran.anahtar == "altin_gumus"]
    assert r.yuzdelik == 1.0 and r.uc
    g = gram_altin(t)
    assert g is not None and round(float(g.iloc[-1]), 2) == round(200 * 40 / 31.1034768, 2)
    assert rekor_mu(g)


def test_cot_net_ve_yuzdelik() -> None:
    satirlar = [
        {
            "report_date_as_yyyy_mm_dd": f"2026-10-{20 - i:02d}T00:00:00.000",
            "m_money_positions_long_all": str(1000 - i * 10),
            "m_money_positions_short_all": "100",
            "open_interest_all": "5000",
        }
        for i in range(10)
    ]
    p = raporlar.cot("088691", "GC=F", al=lambda u, q: satirlar)
    assert (p.net, p.degisim, p.donem) == (900, 10, "2026-10-20")
    assert p.yuzdelik == 1.0 and p.uc


def test_eia_stok() -> None:
    veri = {
        "response": {
            "data": [{"period": f"p{i}", "value": str(400000 - i * 1000)} for i in range(60)]
        }
    }
    s = raporlar.eia_stok(raporlar.PETROL[0], al=lambda u, q: veri)
    assert (s.donem, s.deger, s.degisim) == ("p0", 400.0, 1.0)
    assert s.yil_once == 348.0


def _tablolar(_: list[str]) -> dict[str, pd.DataFrame]:
    return {s: _df(_yuruyus(i)) for i, s in enumerate(TUM_SEMBOLLER)}


def test_kuru_kosu_kart_uretir(tmp_path: Path) -> None:
    rapor: dict[str, Any] = {}
    sonuc = c.calistir(
        kuru=True,
        cikti=tmp_path / "cikti",
        veri_dizini=tmp_path / "veri",
        simdi=datetime.datetime(2026, 10, 27, 23, tzinfo=datetime.timezone.utc),
        indir=_tablolar,
        rapor_kaynagi=lambda: rapor,
    )
    assert sonuc["durum"] == "kuru" and sonuc["kart_sayisi"] >= 3
    assert len(list((tmp_path / "cikti").glob("*.png"))) == sonuc["kart_sayisi"]


def test_tatilde_islem_yok(tmp_path: Path) -> None:
    sonuc = c.calistir(
        kuru=False,
        veri_dizini=tmp_path,
        simdi=datetime.datetime(2026, 10, 29, 23, tzinfo=datetime.timezone.utc),
        indir=_tablolar,
        rapor_kaynagi=dict,
    )
    assert sonuc["durum"] == "islem_yok"


def test_gonderim_kaydi_ve_rapor_tekrarlanmaz(tmp_path: Path, monkeypatch: Any) -> None:
    gidenler: list[str] = []

    def sahte(token: str, hedef: str, gun: str, liste: Any, kayit: Any, **_: Any) -> None:
        gidenler.extend(g.kart for g in liste)

    monkeypatch.setattr(c, "sirayla_gonder", lambda istek, *a, **k: sahte(*a, **k))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_HEDEF", "@rasathane:281")
    stok = raporlar.Stok(raporlar.DOGALGAZ, "2026-10-16", 3800.0, 50.0, 3700.0)
    simdi = datetime.datetime(2026, 10, 27, 23, tzinfo=datetime.timezone.utc)
    ortak: dict[str, Any] = {
        "cikti": tmp_path / "c",
        "veri_dizini": tmp_path / "v",
        "indir": _tablolar,
    }
    s1 = c.calistir(False, simdi=simdi, rapor_kaynagi=lambda: {"eia_gaz": [stok]}, **ortak)
    assert s1["durum"] == "gonderildi" and "eia_gaz:2026-10-16" in gidenler
    s2 = c.calistir(False, simdi=simdi, rapor_kaynagi=lambda: {"eia_gaz": [stok]}, **ortak)
    assert s2["durum"] == "zaten_gonderildi"
