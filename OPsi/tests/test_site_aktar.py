"""Site dışa aktarımı: OPsi kanal ve ETF sayfaları `site-veri/opsi/` altına doğru şemayla yazılır."""

import datetime
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from opsi import site_aktar
from opsi.etf import calistir as etf_calistir
from opsi.etf import liste
from opsi.etf.ekler import AkisSatiri, OpsiyonSatiri, RejimSatiri
from opsi.etf.tarama import Sinyal, olc
from opsi.kanal.gecmis import Kayit
from opsi.kanal.olcum import CspAday

KOK_BOLUM = "opsi"
YASAK = re.compile(r"\b(al|sat|sinyal|öneri|fırsat)\b", re.IGNORECASE)
SIMDI = datetime.datetime(2026, 10, 23, 22, 30, tzinfo=datetime.UTC)


def _sayfa(kok: Path, ad: str) -> dict[str, Any]:
    veri = json.loads((kok / KOK_BOLUM / f"{ad}.json").read_text(encoding="utf-8"))
    assert veri["sema"] == 1 and veri["bolum"] == KOK_BOLUM and veri["sayfa"] == ad
    return veri


def _seri_kontrol(kok: Path, sayfa: dict[str, Any]) -> None:
    """Her satırın seri anahtarı varsa o seri dosyası yazılmış olmalı."""
    for satir in sayfa["satirlar"]:
        anahtar = satir.get("seri")
        if anahtar:
            assert (kok / KOK_BOLUM / "seri" / f"{anahtar}.json").exists(), anahtar


def _yasakli_metin_yok(sayfa: dict[str, Any]) -> None:
    metinler = [sayfa["baslik"], sayfa["aciklama"], *(s["baslik"] for s in sayfa["sutunlar"])]
    metinler += [str(v) for satir in sayfa["satirlar"] for k, v in satir.items() if k != "seri"]
    for metin in metinler:
        assert not YASAK.search(metin), metin


def _gunler(son: str, n: int) -> list[str]:
    return [d.date().isoformat() for d in pd.bdate_range(end=son, periods=n)]


def _kayitlar(gun: str, semboller: list[str], gun_no: int) -> list[Kayit]:
    out: list[Kayit] = []
    for i, s in enumerate(semboller):
        iv = 0.30 + 0.01 * i + 0.004 * gun_no * (i % 3 - 1)
        out.append(
            {
                "tarih": gun,
                "sembol": s,
                "kapanis": 20.0 + i + 0.1 * gun_no,
                "iv30": iv,
                "skew25": 1.0 + i / 20,
                "atm_iv": iv * 0.98,
                "bilanco_gun": 3 if i == 0 else 40,
            }
        )
    return out


def test_kanal_site_sayfalari_ve_serileri(tmp_path: Path) -> None:
    semboller = [f"S{i}" for i in range(12)]
    gunler = _gunler("2026-10-23", 6)
    tum = [k for n, g in enumerate(gunler) for k in _kayitlar(g, semboller, n)]
    gecmis = [k for k in tum if k["tarih"] != gunler[-1]]
    bugun = [k for k in tum if k["tarih"] == gunler[-1]]
    adaylar: list[CspAday] = [
        {"sembol": s, "skor": 50.0 + i, "strike": 30.0, "dte": 30, "sermaye": 3000.0}
        for i, s in enumerate(semboller[:6])
    ]
    adlar = {s: f"{s} Inc" for s in semboller}

    yollar = site_aktar.kanal_aktar(tmp_path, SIMDI, gecmis, bugun, adaylar, adlar)

    assert {p.stem for p in yollar} == {
        "opsiyon-taramasi",
        "iv-durumu",
        "iv-sarsintisi",
        "asagi-yon-primi",
    }
    tarama = _sayfa(tmp_path, "opsiyon-taramasi")
    assert len(tarama["satirlar"]) == 5 and {r["bant"] for r in tarama["satirlar"]} == {"$2k–5k"}
    iv = _sayfa(tmp_path, "iv-durumu")
    assert len(iv["satirlar"]) == len(semboller)
    assert iv["satirlar"][0]["seri"] == "iv-S0" and iv["satirlar"][0]["bilanco"] == "Yakın"
    sarsinti = _sayfa(tmp_path, "iv-sarsintisi")
    assert sarsinti["satirlar"] and sarsinti["satirlar"][0]["tarih"] == gunler[-1]
    prim = _sayfa(tmp_path, "asagi-yon-primi")
    assert len(prim["satirlar"]) == 6
    for ad in ("opsiyon-taramasi", "iv-durumu", "iv-sarsintisi", "asagi-yon-primi"):
        s = _sayfa(tmp_path, ad)
        _seri_kontrol(tmp_path, s)
        _yasakli_metin_yok(s)
    seri = json.loads((tmp_path / KOK_BOLUM / "seri" / "fiyat-S0.json").read_text("utf-8"))
    assert len(seri["noktalar"]) == len(gunler) and seri["birim"] == "$"


def test_kanal_site_gecmissiz_bos_sayfa(tmp_path: Path) -> None:
    """İlk koşuda geçmiş yok: sayfalar yazılır, sarsıntı ve prim boş kalır, hata çıkmaz."""
    bugun = _kayitlar("2026-10-23", ["S0", "S1"], 0)
    site_aktar.kanal_aktar(tmp_path, SIMDI, [], bugun, [], {"S0": "A", "S1": "B"})
    assert _sayfa(tmp_path, "iv-sarsintisi")["satirlar"] == []
    assert _sayfa(tmp_path, "opsiyon-taramasi")["satirlar"] == []


def _fiyat_tablosu(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    kapanis = 50 * np.cumprod(1 + rng.normal(0.0005, 0.01, n))
    idx = pd.bdate_range(end="2026-10-23", periods=n)
    return pd.DataFrame(
        {
            "Close": kapanis,
            "High": kapanis * 1.01,
            "Low": kapanis * 0.99,
            "Volume": np.full(n, 2e6),
        },
        index=idx,
    )


def test_etf_site_sayfalari_ve_serileri(tmp_path: Path) -> None:
    tablolar = {f"E{i}": _fiyat_tablosu(300, i) for i in range(15)}
    tablolar["SPY"] = _fiyat_tablosu(300, 99)
    adlar = {s: f"{s} Fund" for s in tablolar if s != "SPY"}
    kayit: dict[str, liste.Etf] = {
        s: {"sembol": s, "ad": adlar[s], "kaldirac": False, "ilk_gorulme": ""} for s in adlar
    }
    kayit["E13"]["ilk_gorulme"] = "2026-10-20"
    kayit["E14"]["ilk_gorulme"] = "2026-10-21"
    olcumler = {s: o for s in adlar if (o := olc(s, tablolar[s])) is not None}
    kayit_csv = tmp_path / "sinyal_kaydi.csv"
    kayit_csv.write_text("tarih,tur,sembol\n2026-10-22,zirve_52,E1\n", encoding="utf-8")
    bugun_hareketler = [
        Sinyal("zirve_52", "E2", 60.0, 0.01, 59.0, 2e6),
        Sinyal("altin", "E3", 60.0, 0.01, 0.0, 2e6),
    ]
    akis = [AkisSatiri("E4", "E4 Fund", 5e6, 0.1), AkisSatiri("E5", "E5 Fund", -3e6, -0.05)]
    opsiyon = [OpsiyonSatiri("E6", "çağrı", 1000, 500, 2.0, 0.8, "45 C 21.11")]
    rejim = [RejimSatiri("Lüks / temel tüketim", "XLY", "XLP", "risk iştahı", 1.1, 0.02, True)]

    yollar = site_aktar.etf_aktar(
        tmp_path,
        SIMDI,
        "2026-10-23",
        tablolar,
        olcumler,
        kayit,
        adlar,
        rejim,
        opsiyon,
        akis,
        bugun_hareketler,
        kayit_csv,
    )

    assert len(yollar) == 7
    hareketler = _sayfa(tmp_path, "etf-hareketler")
    semboller = [r["sembol"] for r in hareketler["satirlar"]]
    assert semboller.count("E1") == 1 and "E2" in semboller and "E3" in semboller
    yeni = _sayfa(tmp_path, "etf-yeni")
    assert {r["sembol"] for r in yeni["satirlar"]} == {"E13", "E14"}
    akis_s = _sayfa(tmp_path, "etf-akis")
    assert [r["yon"] for r in akis_s["satirlar"]] == ["Giriş", "Çıkış"]
    assert _sayfa(tmp_path, "etf-opsiyon")["satirlar"][0]["oran"] == 2.0
    assert _sayfa(tmp_path, "etf-rejim")["satirlar"][0]["sma50"] == "Üstünde"
    _sayfa(tmp_path, "etf-tema-haritasi")
    _sayfa(tmp_path, "etf-temalar")
    for ad in (
        "etf-rejim",
        "etf-opsiyon",
        "etf-hareketler",
        "etf-yeni",
        "etf-tema-haritasi",
        "etf-temalar",
        "etf-akis",
    ):
        sayfa = _sayfa(tmp_path, ad)
        _seri_kontrol(tmp_path, sayfa)
        _yasakli_metin_yok(sayfa)
    seri = json.loads((tmp_path / KOK_BOLUM / "seri" / "etf-E2.json").read_text("utf-8"))
    assert seri["isaretler"] == [["2026-10-23", "52 Haftanın Zirvesi"]]


def test_etf_site_kuru_kosu_yazar_veri_yazmaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ETF kuru koşusu: site sayfaları yazılır, kayıt klasörü (veri) oluşmaz."""
    gunler = _gunler("2026-10-23", 20)
    monkeypatch.setattr(etf_calistir, "_spy_gunleri", lambda: gunler)
    tablolar = {f"E{i}": _fiyat_tablosu(300, i) for i in range(10)}
    tablolar["SPY"] = _fiyat_tablosu(300, 77)
    guncel: dict[str, liste.Guncel] = {
        s: {"ad": f"{s} Fund", "fiyat": 10.0} for s in tablolar if s != "SPY"
    }
    site = tmp_path / "site-veri"
    etf_calistir.calistir(
        kuru=True,
        tarih="2026-10-23",
        cikti=tmp_path / "c",
        veri=tmp_path / "v",
        indir=lambda _s: tablolar,
        liste_kaynagi=lambda: guncel,
        zincir_kaynagi=lambda _s, _b: {},
        hisse_kaynagi=lambda _s: [],
        varlik_kaynagi=lambda _s: {},
        site_dizini=site,
    )
    assert (site / KOK_BOLUM / "etf-akis.json").exists()
    assert (site / KOK_BOLUM / "etf-temalar.json").exists()
    assert not (tmp_path / "v").exists()
