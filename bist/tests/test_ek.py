from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from rasathane_bist.bulten import PaySatiri, pay_bulteni_csv_oku
from rasathane_bist.calistir import calistir
from rasathane_bist.gecmis import gecmis_oku, gecmis_yaz, geri_doldur, gun_ozeti
from rasathane_bist.site_ek import ek_sayfalar
from rasathane_bist.viop import ViopSatiri, dayanak_kanonik, viop_bulteni_oku

VERI = Path(__file__).parent / "veri"
GUN = date(2026, 10, 23)
SIMDI = datetime(2026, 10, 23, 18, tzinfo=timezone.utc)


def _satirlar() -> list[ViopSatiri]:
    return viop_bulteni_oku((VERI / "viop_ornek.csv").read_bytes())[1]


def _pay() -> list[PaySatiri]:
    return pay_bulteni_csv_oku((VERI / "thb_ornek.csv").read_bytes().decode("latin-1"))[1]


def _oku(yol: Path) -> Any:
    return json.loads(yol.read_text("utf-8"))


def test_dayanak_kanonik_vadeli_ve_opsiyon_ayni_anahtar() -> None:
    satirlar = _satirlar()
    vadeli = {dayanak_kanonik(s) for s in satirlar if s.kod.startswith("F_")}
    assert {"XU030", "THYAO", "USDTRY"} <= vadeli


def test_gun_ozeti_opsiyon_tur_ayrimi() -> None:
    ozet = gun_ozeti(_satirlar())
    xu = ozet["dayanak"]["XU030"]
    assert xu["vadeli_hacim"] > 0
    assert xu["cagri_hacim"] > 0 and xu["put_hacim"] > 0
    assert ozet["dayanak"]["THYAO"]["on_uzlasma"] == 259.7


def test_geri_doldur_hafta_sonu_atlar_ve_tatili_isaretler() -> None:
    bayt = (VERI / "viop_ornek.csv").read_bytes()

    def indir(url: str) -> tuple[int, bytes]:
        return (200, bayt) if url.endswith("viop_20261023.csv") else (404, b"")

    gecmis: dict[str, Any] = {}
    eklenen = geri_doldur(gecmis, date(2026, 10, 25), indir, gun_sayisi=5)
    assert eklenen == 1
    assert "dayanak" in gecmis["2026-10-23"]
    assert gecmis["2026-10-22"] is None  # Perşembe: tatil/yok olarak işaretlenir
    assert "2026-10-24" not in gecmis  # Cumartesi hiç istenmez


def test_gecmis_yaz_oku_gidis_donus(tmp_path: Path) -> None:
    yol = tmp_path / "g.json"
    gecmis: dict[str, Any] = {"2026-10-23": gun_ozeti(_satirlar()), "2026-10-22": None}
    gecmis_yaz(yol, gecmis)
    assert gecmis_oku(yol) == gecmis


def test_ek_sayfalar_iki_gun_seri_ve_degisim(tmp_path: Path) -> None:
    satirlar = _satirlar()
    onceki = [dataclasses.replace(s, acik_pozisyon=s.acik_pozisyon // 2) for s in satirlar]
    gecmis: dict[str, Any] = {
        "2026-10-22": gun_ozeti(onceki),
        "2026-10-23": gun_ozeti(satirlar),
    }
    ek_sayfalar(tmp_path, GUN, satirlar, _pay(), gecmis, {}, None, SIMDI)
    kok = tmp_path / "viop"

    acik = _oku(kok / "acik-pozisyon.json")["satirlar"]
    xu = next(r for r in acik if r["dayanak"] == "XU030")
    assert xu["degisim"] is not None and xu["degisim"] > 0
    seri = _oku(kok / "seri" / "acik-xu030.json")
    assert [n[0] for n in seri["noktalar"]] == ["2026-10-22", "2026-10-23"]

    pc = _oku(kok / "put-call.json")["satirlar"]
    assert any(r["dayanak"] == "XU030" and r["oran_hacim"] > 0 for r in pc)
    assert (kok / "seri" / "putcall-xu030.json").is_file()


def test_takvim_ve_egri(tmp_path: Path) -> None:
    satirlar = _satirlar()
    ek_sayfalar(tmp_path, GUN, satirlar, [], {"2026-10-23": gun_ozeti(satirlar)}, {}, None, SIMDI)
    kok = tmp_path / "viop"

    takvim = _oku(kok / "takvim.json")["satirlar"]
    vadeler = [r["vade"] for r in takvim]
    assert vadeler == sorted(vadeler)
    assert all(v >= "2026-10-23" for v in vadeler)

    egri = _oku(kok / "vade-egrisi.json")["satirlar"]
    xu = next(r for r in egri if r["dayanak"] == "XU030")
    assert xu["yakin_vade"] <= xu["uzak_vade"]
    seri = _oku(kok / "seri" / "egri-xu030.json")
    assert len(seri["noktalar"]) >= 1


def test_varant_faiz_yoksa_kaldirac_yok(tmp_path: Path) -> None:
    ek_sayfalar(tmp_path, GUN, [], _pay(), {}, {}, None, SIMDI)
    varant = _oku(tmp_path / "viop" / "varant.json")
    assert varant["satirlar"]
    assert all(r["kaldirac"] is None for r in varant["satirlar"])
    assert "hesaplanmadı" in varant["aciklama"]


def test_varant_faiz_ve_spot_ile_kaldirac(tmp_path: Path) -> None:
    ek_sayfalar(tmp_path, GUN, [], _pay(), {}, {"XU030": 14000.0}, 0.36, SIMDI)
    varant = _oku(tmp_path / "viop" / "varant.json")["satirlar"]
    hesaplananlar = [r for r in varant if r["dayanak"] == "XU030" and r["kaldirac"] is not None]
    assert hesaplananlar
    assert all(r["kaldirac"] > 0 for r in hesaplananlar)


def test_calistir_gecmis_dosyasini_biriktirir(tmp_path: Path) -> None:
    bayt = (VERI / "viop_ornek.csv").read_bytes()

    def indir(url: str) -> tuple[int, bytes]:
        return (200, bayt) if url.endswith("viop_20261023.csv") else (404, b"")

    yol = tmp_path / "gecmis.json"
    calistir(
        tmp_path / "site", bugun=date(2026, 10, 25), indir=indir, endeks=False, gecmis_yolu=yol
    )
    veri = gecmis_oku(yol)
    assert "2026-10-23" in veri
    assert (tmp_path / "site" / "viop" / "acik-pozisyon.json").is_file()
    assert (tmp_path / "site" / "viop" / "varant.json").is_file()


def test_on_vade_seri_ve_gostergeler(tmp_path: Path) -> None:
    from rasathane_bist.site_ek import _ema, _rsi

    assert _ema([1.0, 2.0, 3.0], 3)[:2] == [None, None]
    assert _ema([1.0, 2.0, 3.0], 3)[2] is not None
    assert _rsi([1.0, 2.0, 3.0], 14) == [None, None, None]
    yukari = _rsi([float(i) for i in range(1, 30)], 14)
    assert yukari[-1] == 100.0

    satirlar = _satirlar()
    gecmis: dict[str, Any] = {"2026-10-23": gun_ozeti(satirlar)}
    ek_sayfalar(tmp_path, GUN, satirlar, [], gecmis, {}, None, SIMDI)
    kok = tmp_path / "viop"
    sayfa = _oku(kok / "on-vade.json")["satirlar"]
    assert any(r["dayanak"] == "THYAO" for r in sayfa)
    seri = _oku(kok / "seri" / "fiyat-thyao.json")
    assert seri["tarihler"] == ["2026-10-23"]
    assert seri["sutunlar"]["kapanis"] == [259.7]
    assert (kok / "seri" / "fiyat-thyao-hafta.json").is_file()
