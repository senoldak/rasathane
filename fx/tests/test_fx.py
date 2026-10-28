import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rasathane_fx import analiz, raporlar
from rasathane_fx import calistir as c
from rasathane_fx.evren import TUM_SEMBOLLER
from rasathane_fx.tarama import kapanis, olc, sinyaller

GUN = pd.bdate_range(end="2026-10-27", periods=1300)


def _df(seri: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"Close": seri}, index=GUN[-len(seri) :])


def _yuruyus(tohum: int, son_adim: float = 0.0) -> np.ndarray:
    r = np.random.default_rng(tohum).normal(0, 0.005, len(GUN))
    r[-1] = son_adim
    return np.asarray(100 * np.exp(np.cumsum(r)))


def test_sert_hareket_ve_zirve() -> None:
    seri = _yuruyus(1)
    seri[-1] = seri[:-1].max() * 1.03
    df = _df(seri)
    o = olc("EURUSD=X", df)
    assert o is not None and o.z is not None and o.z > 2.5
    turler = {s.tur for s in sinyaller("EURUSD=X", df, o)}
    assert {"yukselis", "zirve_52"} <= turler


def test_tek_gunluk_sivri_atilir() -> None:
    seri = np.full(10, 5.0)
    seri[5] = 5.4
    assert len(kapanis(_df(seri))) == 9


def test_carry_ve_risk() -> None:
    t = {s: _df(_yuruyus(i)) for i, s in enumerate(TUM_SEMBOLLER)}
    cs = analiz.carry({"USD": 4.0, "TRY": 40.0, "JPY": 0.5}, t)
    assert [x.para for x in cs] == ["TRY", "JPY"] and cs[0].fark == 36.0
    r = analiz.risk(t)
    assert r is not None and 0 <= r.yuzdelik <= 1


def test_karne_yonlu_getiri() -> None:
    seri = np.linspace(100, 200, len(GUN))
    t = {"EURUSD=X": _df(seri)}
    tarih = GUN[-100].date().isoformat()
    (k,) = analiz.karne([{"tarih": tarih, "tur": "dusus", "sembol": "EURUSD=X"}], t)
    assert k.ortalama[5] < 0 and k.isabet[20] == 0.0


def test_cot_net_ve_yuzdelik() -> None:
    satirlar = [
        {
            "report_date_as_yyyy_mm_dd": f"2026-10-{20 - i:02d}T00:00:00.000",
            "lev_money_positions_long": str(1000 - i * 10),
            "lev_money_positions_short": "100",
            "open_interest_all": "5000",
        }
        for i in range(10)
    ]
    p = raporlar.cot("099741", "EUR", al=lambda u, q: satirlar)
    assert (p.net, p.degisim, p.donem) == (900, 10, "2026-10-20")
    assert p.yuzdelik == 1.0 and p.uc


def test_bis_faizleri() -> None:
    metin = "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\nD,US,2026-10-20,3.875\nD,TR,2026-10-16,37\n"
    assert raporlar.politika_faizleri(al=lambda u, q: metin) == {"USD": 3.875, "TRY": 37.0}


def _kaynaklar(faizler: dict[str, float] | None = None) -> c.Kaynaklar:
    return c.Kaynaklar(
        indir=lambda s: {x: _df(_yuruyus(i)) for i, x in enumerate(TUM_SEMBOLLER)},
        saatlik=lambda s: {},
        hisseler=lambda g: {},
        faizler=lambda: faizler or {"USD": 3.875, "EUR": 2.5, "TRY": 37.0},
        tahviller=dict,
        cot=list,
    )


_SIMDI = datetime.datetime(2026, 10, 27, 23, tzinfo=datetime.timezone.utc)


def test_kuru_kosu_kart_uretir(tmp_path: Path) -> None:
    sonuc = c.calistir(
        kuru=True,
        cikti=tmp_path / "cikti",
        veri_dizini=tmp_path / "veri",
        simdi=_SIMDI,
        kaynaklar=_kaynaklar(),
    )
    assert sonuc["durum"] == "kuru" and sonuc["kart_sayisi"] >= 2
    assert len(list((tmp_path / "cikti").glob("*.png"))) == sonuc["kart_sayisi"]


def test_tatilde_islem_yok(tmp_path: Path) -> None:
    simdi = datetime.datetime(2026, 10, 29, 23, tzinfo=datetime.timezone.utc)
    sonuc = c.calistir(kuru=False, veri_dizini=tmp_path, simdi=simdi, kaynaklar=_kaynaklar())
    assert sonuc["durum"] == "islem_yok"


def test_faiz_karari_ve_tekrar_yok(tmp_path: Path, monkeypatch: Any) -> None:
    gidenler: list[str] = []

    def sahte(token: str, hedef: str, gun: str, liste: Any, kayit: Any, **_: Any) -> None:
        gidenler.extend(g.kart for g in liste)

    monkeypatch.setattr(c, "sirayla_gonder", lambda istek, *a, **k: sahte(*a, **k))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_HEDEF", "@rasathane:295")
    v = tmp_path / "v"
    v.mkdir()
    (v / "durum.json").write_text('{"faizler": {"USD": 4.125}}', encoding="utf-8")
    ortak: dict[str, Any] = {"cikti": tmp_path / "c", "veri_dizini": v, "simdi": _SIMDI}
    s1 = c.calistir(False, kaynaklar=_kaynaklar(), **ortak)
    assert s1["durum"] == "gonderildi" and "faiz_karari:2026-10-27" in gidenler
    s2 = c.calistir(False, kaynaklar=_kaynaklar(), **ortak)
    assert s2["durum"] == "zaten_gonderildi"
