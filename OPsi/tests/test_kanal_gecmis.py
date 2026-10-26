"""Kanal IV geçmişi ve gönderim kaydı."""

from pathlib import Path

from opsi.kanal.gecmis import (
    Kayit,
    gonderildi_isaretle,
    gonderildi_mi,
    gun_yaz,
    iv_konum,
    iv_seri,
    oku,
    onceki_gun,
)


def kayit(tarih: str, sembol: str, **k: object) -> Kayit:
    base: dict[str, object] = {
        "tarih": tarih,
        "sembol": sembol,
        "kapanis": 10.0,
        "iv30": 0.3,
        "skew25": 1.1,
        "atm_iv": 0.3,
        "bilanco_gun": 40,
    }
    base.update(k)
    return base  # type: ignore[return-value]


def test_ayni_gun_yeniden_yazinca_satir_cogalmaz(tmp_path: Path) -> None:
    y = tmp_path / "g.csv"
    gun_yaz([kayit("2026-10-23", "AAPL", iv30=0.3)], y)
    gun_yaz([kayit("2026-10-23", "AAPL", iv30=0.31)], y)
    assert [(k["tarih"], k["iv30"]) for k in oku(y)] == [("2026-10-23", 0.31)]


def test_baska_gunler_korunur(tmp_path: Path) -> None:
    y = tmp_path / "g.csv"
    gun_yaz([kayit("2026-10-22", "F")], y)
    gun_yaz([kayit("2026-10-23", "F")], y)
    assert [k["tarih"] for k in oku(y)] == ["2026-10-22", "2026-10-23"]


def test_bos_degerler_none_olarak_doner(tmp_path: Path) -> None:
    y = tmp_path / "g.csv"
    gun_yaz([kayit("2026-10-23", "F", iv30=None, skew25=None, bilanco_gun=None)], y)
    k = oku(y)[0]
    assert k["iv30"] is None and k["skew25"] is None and k["bilanco_gun"] is None
    assert k["kapanis"] == 10.0


def test_dosya_yoksa_bos_liste(tmp_path: Path) -> None:
    assert oku(tmp_path / "yok.csv") == []


def test_onceki_gun_atlanan_gunu_gecer() -> None:
    k = [kayit("2026-10-20", "F"), kayit("2026-10-23", "F")]
    assert onceki_gun(k, "2026-10-23") == "2026-10-20"
    assert onceki_gun(k, "2026-10-20") is None


def test_iv_seri_none_atlar_ve_sinirlar() -> None:
    k = [
        kayit("2026-10-20", "F", iv30=0.2),
        kayit("2026-10-21", "F", iv30=None),
        kayit("2026-10-22", "F", iv30=0.3),
        kayit("2026-10-23", "F", iv30=0.4),
        kayit("2026-10-22", "G", iv30=0.9),
    ]
    assert iv_seri(k, "F", "2026-10-22") == [0.2, 0.3]


def test_iv_konum_etiketleri() -> None:
    assert iv_konum([0.2, 0.3, 0.4], "2026-10-21")[1] == "IV yüzd. (21.10'dan beri)"
    v, etiket = iv_konum([0.2] * 251 + [0.4], "2025-10-01")
    assert (v, etiket) == (1.0, "IV Rank (1 yıl)")


def test_iv_konum_yuzdelik_degeri() -> None:
    assert iv_konum([0.2, 0.3, 0.4, 0.5], "2026-10-21")[0] == 1.0
    assert iv_konum([0.5, 0.4, 0.3, 0.2], "2026-10-21")[0] == 0.25


def test_iv_konum_sabit_seri_orta() -> None:
    assert iv_konum([0.3] * 300, "2025-01-01")[0] == 0.5


def test_gonderildi_kaydi(tmp_path: Path) -> None:
    y = tmp_path / "s.json"
    assert not gonderildi_mi("2026-10-23", y)
    gonderildi_isaretle("2026-10-23", y)
    gonderildi_isaretle("2026-10-23", y)
    assert gonderildi_mi("2026-10-23", y)
    assert not gonderildi_mi("2026-10-24", y)
