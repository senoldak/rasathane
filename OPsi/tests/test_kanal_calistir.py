"""Kanal günlük akışı: ölçüm, SPY takvimi ve Telegram taklit edilir; dosyalar tmp_path'te."""

import datetime
from pathlib import Path
from typing import Any

import pytest

from opsi.kanal import calistir as c
from opsi.kanal.calistir import bugunun_kartlari, calistir
from opsi.kanal.evren import EvrenSatiri
from opsi.kanal.gecmis import oku
from opsi.kanal.olcum import Olcum


def dt(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)


SALI = dt("2026-10-20T22:30Z")
CARSAMBA = dt("2026-10-21T22:30Z")
CUMA = dt("2026-10-23T22:30Z")
SEMBOLLER = [f"S{i}" for i in range(10)]


def _islem_gunleri(son: str) -> list[str]:
    g, out = datetime.date(2026, 9, 1), []
    while g.isoformat() <= son:
        if g.weekday() < 5 and g.isoformat() not in {"2026-11-26"}:
            out.append(g.isoformat())
        g += datetime.timedelta(days=1)
    return out


class Ortam:
    def __init__(self, veri: Path) -> None:
        self.veri = veri
        self.spy_son: str | None = None
        self.okunamayan = 0.0
        self.gonderimler: list[tuple[str, str, str]] = []
        self.sahibe: list[str] = []
        self.hatali_kart: str | None = None  # bu kartta bir kez kalıcı hata


@pytest.fixture
def ortam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ortam:
    o = Ortam(tmp_path / "kanal_veri")
    o.veri.mkdir()
    (o.veri / "evren.csv").write_text(
        "sembol,ad,etf\n" + "".join(f"{s},{s} Inc,0\n" for s in SEMBOLLER), encoding="utf-8"
    )

    def gecmis(sembol: str, period: str = "1y") -> list[tuple[str, float]]:
        assert sembol == "SPY"
        son = o.spy_son
        return [(d, 500.0) for d in _islem_gunleri(son or "2099-01-01")][-25:]

    def olc(
        satir: EvrenSatiri, tarih: str, iv_gecmisi: list[float], now: Any = None
    ) -> Olcum | None:
        i = int(satir["sembol"][1:])
        if i < 10 * o.okunamayan:
            return None
        gun = int(tarih[-2:])
        iv = 0.3 + 0.01 * i + 0.02 * ((i * gun) % 7)
        return {
            "kayit": {
                "tarih": tarih,
                "sembol": satir["sembol"],
                "kapanis": 20.0 + i,
                "iv30": iv,
                "skew25": 1.0 + i / 20,
                "atm_iv": iv,
                "bilanco_gun": 40,
            },
            "csp": {
                "sembol": satir["sembol"],
                "skor": 50.0 + i,
                "strike": 30.0,
                "dte": 30,
                "sermaye": 3000.0,
            },
        }

    def gonder(token: str, hedef: str, gun: str, gidenler: list[Any], kayit: Any) -> list[int]:
        ids = []
        for g in gidenler:
            if kayit.gonderildi_mi(gun, g.kart, g.sayfa):
                continue
            if g.kart == o.hatali_kart:
                o.hatali_kart = None
                raise RuntimeError("Bad Request: TOPIC_CLOSED")
            o.gonderimler.append((hedef, g.kart, g.aciklama))
            kayit.ekle(gun, g.kart, g.sayfa, 1)
            ids.append(1)
        return ids

    monkeypatch.setattr(c.fetch, "get_history", gecmis)
    monkeypatch.setattr(c, "olc", olc)
    monkeypatch.setattr(c, "gonder", gonder)
    monkeypatch.setattr(c, "sahibe_yaz", lambda t, s, m: o.sahibe.append(m))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_HEDEF", "@rasathane:12")
    monkeypatch.setenv("TELEGRAM_SAHIP_ID", "99")
    return o


def kos(o: Ortam, tmp_path: Path, kuru: bool, simdi: datetime.datetime, **kw: Any) -> c.Sonuc:
    return calistir(kuru=kuru, simdi=simdi, veri=o.veri, cikti=tmp_path / "cikti", **kw)


def test_tatil_gunu_hicbir_sey_yazmaz_gondermez(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-11-25"
    r = kos(ortam, tmp_path, False, dt("2026-11-26T22:30Z"))
    assert r["durum"] == "islem_yok"
    assert not (ortam.veri / "iv_gecmisi.csv").exists() and ortam.gonderimler == []


def test_ayni_gun_ikinci_kez_gonderilmez(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-23"
    assert kos(ortam, tmp_path, False, CUMA)["durum"] == "gonderildi"
    assert kos(ortam, tmp_path, False, CUMA)["durum"] == "zaten_gonderildi"
    assert ortam.gonderimler
    assert all(h == "@rasathane:12" for h, _, _ in ortam.gonderimler)
    assert all(
        a.startswith("OPsi · ") and a.endswith(" · 23.10.2026") for _, _, a in ortam.gonderimler
    )


def test_yarida_kalan_gonderim_kaldigi_yerden(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-22"
    kos(ortam, tmp_path, True, dt("2026-10-22T22:30Z"))
    ortam.spy_son = "2026-10-23"
    ortam.hatali_kart = "prim"
    with pytest.raises(RuntimeError):
        kos(ortam, tmp_path, False, CUMA)
    assert [k for _, k, _ in ortam.gonderimler] == ["sarsinti"]
    assert not (ortam.veri / "gonderilenler.json").exists()
    assert kos(ortam, tmp_path, False, CUMA)["durum"] == "gonderildi"
    assert [k for _, k, _ in ortam.gonderimler] == ["sarsinti", "prim"]
    assert ortam.gonderimler[1][2] == "OPsi · Aşağı Yön Primi · 23.10.2026"


def test_eksik_veri_gondermez_sahibe_yazar(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-23"
    ortam.okunamayan = 0.4
    r = kos(ortam, tmp_path, False, CUMA)
    assert r["durum"] == "eksik_veri" and r["okunan_oran"] == pytest.approx(0.6)
    assert ortam.gonderimler == [] and len(ortam.sahibe) == 1
    assert not (ortam.veri / "iv_gecmisi.csv").exists()


def test_carsamba_tek_kart(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-20"
    kos(ortam, tmp_path, True, SALI)
    ortam.spy_son = "2026-10-21"
    r = kos(ortam, tmp_path, True, CARSAMBA)
    assert r["durum"] == "kuru" and r["kart_sayisi"] == 1
    assert len(list((tmp_path / "cikti").glob("2026-10-21_*.png"))) == 1


def test_kuru_kosu_gecmise_yazar_gondermez(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-20"
    kos(ortam, tmp_path, True, SALI)
    assert {k["tarih"] for k in oku(ortam.veri / "iv_gecmisi.csv")} == {"2026-10-20"}
    assert ortam.gonderimler == []
    assert not (ortam.veri / "gonderilenler.json").exists()


def test_gonderim_hatasi_sahibe_yazilir_ve_yukselir(
    ortam: Ortam, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def patla(*a: Any) -> None:
        raise RuntimeError("chat not found")

    monkeypatch.setattr(c, "gonder", patla)
    ortam.spy_son = "2026-10-23"
    with pytest.raises(RuntimeError):
        kos(ortam, tmp_path, False, CUMA)
    assert ortam.sahibe and "chat not found" in ortam.sahibe[0]
    assert not (ortam.veri / "gonderilenler.json").exists()


def test_pazartesi_tatilse_csp_saliya_kayar() -> None:
    assert bugunun_kartlari("2026-01-20", haftanin_ilk_islem_gunu=True) == [
        "sarsinti",
        "csp",
        "prim",
    ]


def test_haftanin_kartlari() -> None:
    assert bugunun_kartlari("2026-10-19", True) == ["sarsinti", "csp"]
    assert bugunun_kartlari("2026-10-21", False) == ["sarsinti"]
    assert bugunun_kartlari("2026-10-22", False) == ["sarsinti", "prim"]


def test_cli_kanal_gizli_yoksa_cikis_2(monkeypatch: pytest.MonkeyPatch) -> None:
    from opsi import cli

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_HEDEF", raising=False)
    assert cli.main(["kanal"]) == 2


def test_cli_kanal_kuru_calistirir(monkeypatch: pytest.MonkeyPatch) -> None:
    from opsi import cli

    cagri: list[dict[str, Any]] = []

    def sahte(**k: Any) -> c.Sonuc:
        cagri.append(k)
        return {"durum": "kuru", "kart_sayisi": 2, "okunan_oran": 0.9}

    monkeypatch.setattr(c, "calistir", sahte)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert cli.main(["kanal", "--kuru", "--tarih", "2026-10-23"]) == 0
    assert cagri == [{"kuru": True, "tarih": "2026-10-23", "grafik_fiyat": cli.get_history}]


def test_spy_verisi_yoksa_sahibe_yazar_ve_hata(
    ortam: Ortam, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(c.fetch, "get_history", lambda s, p="1y": [])
    r = kos(ortam, tmp_path, False, CUMA)
    assert r["durum"] == "spy_yok" and len(ortam.sahibe) == 1 and ortam.gonderimler == []


def test_gecmis_tarih_reddedilir(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-23"
    with pytest.raises(ValueError):
        calistir(kuru=True, tarih="2026-10-20", simdi=CUMA, veri=ortam.veri, cikti=tmp_path / "c")
    assert not (ortam.veri / "iv_gecmisi.csv").exists()


def test_bozuk_tarih_reddedilir(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-23"
    with pytest.raises(ValueError):
        calistir(kuru=True, tarih="2026-1-5", simdi=CUMA, veri=ortam.veri, cikti=tmp_path / "c")


def test_son_seans_tarihi_kabul(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-23"
    r = calistir(kuru=True, tarih="2026-10-23", simdi=CUMA, veri=ortam.veri, cikti=tmp_path / "c")
    assert r["durum"] == "kuru"


def test_cli_eksik_veri_sifir_disi(monkeypatch: pytest.MonkeyPatch) -> None:
    from opsi import cli

    monkeypatch.setattr(
        c, "calistir", lambda **k: {"durum": "spy_yok", "kart_sayisi": 0, "okunan_oran": 0.0}
    )
    assert cli.main(["kanal", "--kuru"]) == 1


def _fiyat_gecmisi(sembol: str, period: str = "6mo") -> list[tuple[str, float]]:
    son = datetime.date(2026, 10, 23)
    return [
        ((son - datetime.timedelta(days=150 - i)).isoformat(), 50.0 + (i % 5)) for i in range(151)
    ]


def test_grafik_gunun_kartlarindan_sonra(ortam: Ortam, tmp_path: Path) -> None:
    ortam.spy_son = "2026-10-22"
    kos(ortam, tmp_path, True, dt("2026-10-22T22:30Z"))
    ortam.spy_son = "2026-10-23"
    assert kos(ortam, tmp_path, False, CUMA, grafik_fiyat=_fiyat_gecmisi)["durum"] == "gonderildi"
    assert [k for _, k, _ in ortam.gonderimler] == ["sarsinti", "prim", "grafik"]
    assert ortam.gonderimler[-1][2] == "OPsi · Oynaklık · 23.10.2026"


def test_grafik_hatasi_kartlari_durdurmaz(ortam: Ortam, tmp_path: Path) -> None:
    def bozuk(sembol: str, period: str = "6mo") -> list[tuple[str, float]]:
        raise RuntimeError("Yahoo kapalı")

    ortam.spy_son = "2026-10-20"
    kos(ortam, tmp_path, True, SALI)
    ortam.spy_son = "2026-10-21"
    r = kos(ortam, tmp_path, False, CARSAMBA, grafik_fiyat=bozuk)
    assert r["durum"] == "gonderildi"
    assert [k for _, k, _ in ortam.gonderimler] == ["sarsinti"]
    assert any("Yahoo kapalı" in m for m in ortam.sahibe)
