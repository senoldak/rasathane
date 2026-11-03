import datetime
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rasathane_fx import analiz, raporlar, site_aktar
from rasathane_fx import calistir as c
from rasathane_fx.calistir import _SEANS_KURLARI
from rasathane_fx.evren import SEPET, TUM_SEMBOLLER
from rasathane_fx.tarama import olc, sepet, sinyaller

GUN = pd.bdate_range(end="2026-10-27", periods=1300)
SIMDI = datetime.datetime(2026, 10, 27, 23, tzinfo=datetime.timezone.utc)
TARIH = "2026-10-27"
YASAK = re.compile(r"\b(al|sat|sinyal|öneri|fırsat)\b", re.IGNORECASE)
FAIZLER = {"USD": 4.0, "EUR": 2.0, "JPY": 0.5, "CHF": 0.0, "AUD": 4.1, "TRY": 40.0, "GBP": 4.0}


def _df(seri: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"Close": seri}, index=GUN[-len(seri) :])


def _yuruyus(tohum: int) -> np.ndarray:
    r = np.random.default_rng(tohum).normal(0, 0.005, len(GUN))
    return np.asarray(100 * np.exp(np.cumsum(r)))


def _tablolar() -> dict[str, pd.DataFrame]:
    zq = [s for s, _ in analiz.zq_sembolleri(GUN[-1].date())]
    return {s: _df(_yuruyus(i)) for i, s in enumerate([*TUM_SEMBOLLER, *zq])}


def _calis(
    kok: Path,
    faizler: dict[str, float] | None = FAIZLER,
    tahvil: bool = True,
    saatlik: bool = True,
    duyarlilik: bool = True,
    pozisyon: bool = True,
) -> list[Path]:
    tablolar = _tablolar()
    olcumler = {s: o for s, df in tablolar.items() if (o := olc(s, df)) is not None}
    sp = sepet(tablolar)
    if sp is not None:
        olcumler[SEPET] = olc(SEPET, sp)  # type: ignore[assignment]
    bulunan = [
        sy for s, df in tablolar.items() if s in olcumler for sy in sinyaller(s, df, olcumler[s])
    ]
    kayit = [
        {"tarih": GUN[-30].date().isoformat(), "tur": "yukselis", "sembol": "EURUSD=X"},
        {"tarih": GUN[-12].date().isoformat(), "tur": "bag", "sembol": "aud_bakir"},
    ]
    gunler = [g.date().isoformat() for g in GUN]
    t = {
        "ABD": pd.Series(np.full(len(GUN), 4.0), index=GUN),
        "EUR": pd.Series(np.full(len(GUN), 2.5), index=GUN),
        "JPY": pd.Series(np.full(len(GUN), 0.5), index=GUN),
    }
    saatlik_veri = None
    if saatlik:
        saat = pd.date_range(end="2026-10-27 20:00", periods=240, freq="h")
        saatlik_veri = {
            s: pd.DataFrame({"Close": np.linspace(1, 1.01, 240) + 0.001 * i}, index=saat)
            for i, s in enumerate(_SEANS_KURLARI)
        }
    return site_aktar.aktar(
        kok,
        SIMDI,
        TARIH,
        tablolar,
        olcumler,
        bulunan,
        gunler,
        kayit,
        faizler or {},
        t if tahvil else None,
        [raporlar.Pozisyon("EUR", "2026-10-20", 900, 10, 0.5, 5000)] if pozisyon else [],
        saatlik_veri,
        [analiz.Duyarlilik("THYAO", 0.5, 0.2)] if duyarlilik else None,
    )


def _oku(yol: Path) -> Any:
    return json.loads(yol.read_text("utf-8"))


def _metinler(veri: Any) -> list[str]:
    if isinstance(veri, str):
        return [veri]
    if isinstance(veri, dict):
        return [m for v in veri.values() for m in _metinler(v)]
    if isinstance(veri, list):
        return [m for v in veri for m in _metinler(v)]
    return []


def test_tum_sayfalar_ve_seriler_yazilir(tmp_path: Path) -> None:
    _calis(tmp_path)
    f = tmp_path / "fx"
    for ad in (
        "pano",
        "hareketler",
        "risk",
        "politika",
        "carry",
        "faiz-farki",
        "fed",
        "baglar",
        "oynaklik",
        "seanslar",
        "fonlar",
        "gecmis-isabet",
        "duyarlilik",
    ):
        assert (f / f"{ad}.json").exists(), ad
    pano = _oku(f / "pano.json")
    assert len(pano["satirlar"]) == 25  # 24 kur + TL sepeti
    gunluk = _oku(f / "seri" / "EURUSD=X.json")
    assert len(gunluk["tarihler"]) == 252
    assert {"kapanis", "ema144", "ema233", "ema377", "rsi14"} <= set(gunluk["sutunlar"])
    haftalik = _oku(f / "seri" / "EURUSD=X-hafta.json")
    assert len(haftalik["tarihler"]) <= 104
    assert (f / "seri" / "sepet.json").exists()
    assert (f / "seri" / "risk-skor.json").exists()
    assert (f / "seri" / "bag-aud_bakir.json").exists()


def test_pano_satirlari_seriye_baglanir(tmp_path: Path) -> None:
    _calis(tmp_path)
    f = tmp_path / "fx"
    for satir in _oku(f / "pano.json")["satirlar"]:
        assert (f / "seri" / f"{satir['seri']}.json").exists(), satir["seri"]


def test_gecmis_isabet_adi_ve_yasak_kelimeler(tmp_path: Path) -> None:
    _calis(tmp_path)
    f = tmp_path / "fx"
    assert _oku(f / "gecmis-isabet.json")["baslik"] == "Geçmiş isabet"
    for yol in f.glob("*.json"):
        for metin in _metinler(_oku(yol)):
            assert not YASAK.search(metin), (yol.name, metin)


def test_her_sayfada_uyari(tmp_path: Path) -> None:
    _calis(tmp_path)
    for yol in (tmp_path / "fx").glob("*.json"):
        if yol.parent.name != "fx":
            continue
        veri = _oku(yol)
        assert "Yatırım tavsiyesi değildir. Veriler gecikmelidir." in veri["aciklama"], yol.name


def test_kaynak_yoksa_ilgili_sayfa_yazilmaz(tmp_path: Path) -> None:
    _calis(tmp_path, faizler={}, tahvil=False, saatlik=False, duyarlilik=False, pozisyon=False)
    f = tmp_path / "fx"
    assert (f / "pano.json").exists()
    assert (f / "hareketler.json").exists()
    for ad in ("politika", "carry", "faiz-farki", "fed", "seanslar", "fonlar", "duyarlilik"):
        assert not (f / f"{ad}.json").exists(), ad


def test_karne_dosyasi_ufuklari_icerir(tmp_path: Path) -> None:
    _calis(tmp_path)
    satirlar = _oku(tmp_path / "fx" / "gecmis-isabet.json")["satirlar"]
    assert {s["ufuk"] for s in satirlar} <= {"5 işlem günü", "20 işlem günü", "60 işlem günü"}
    assert any(s["ad"] == "Sert Yükseliş" for s in satirlar)


def test_calistir_kuru_koşu_siteye_yazar(tmp_path: Path) -> None:
    """Uçtan uca: kaynaklar sahte, gönderim yok; site klasörü dolar, kartlar üretilir."""
    tablolar = _tablolar()
    saat = pd.date_range(end="2026-10-27 20:00", periods=240, freq="h")
    kaynaklar = c.Kaynaklar(
        indir=lambda semboller: {s: tablolar[s] for s in semboller if s in tablolar},
        saatlik=lambda semboller: {
            s: pd.DataFrame({"Close": np.linspace(1, 1.01, 240)}, index=saat) for s in semboller
        },
        hisseler=lambda bugun: {},
        faizler=lambda: FAIZLER,
        tahviller=lambda: {
            "ABD": pd.Series(np.full(len(GUN), 4.0), index=GUN),
            "EUR": pd.Series(np.full(len(GUN), 2.5), index=GUN),
            "JPY": pd.Series(np.full(len(GUN), 0.5), index=GUN),
        },
        cot=lambda: [raporlar.Pozisyon("EUR", "2026-10-20", 900, 10, 0.5, 5000)],
        evds=dict,
    )
    site = tmp_path / "site"
    sonuc = c.calistir(
        kuru=True,
        tarih=TARIH,
        cikti=tmp_path / "cikti",
        simdi=SIMDI,
        veri_dizini=tmp_path / "veri",
        kaynaklar=kaynaklar,
        site_dizini=site,
    )
    assert sonuc["durum"] in {"kuru", "kart_yok"}
    assert (site / "fx" / "pano.json").exists()
    assert (site / "fx" / "fonlar.json").exists()
    assert (site / "fx" / "seri" / "EURUSD=X.json").exists()
