"""Kanal sembol ölçümü: Yahoo çağrıları taklit edilir."""

import datetime

import pytest
from kanal_yardim import NOW, zincir_bs

from opsi import fetch
from opsi.kanal import olcum
from opsi.kanal.evren import EvrenSatiri
from opsi.kanal.olcum import olc, vade_sec


def satir(sembol: str, etf: bool = False) -> EvrenSatiri:
    return {"sembol": sembol, "ad": sembol + " Inc", "etf": etf}


@pytest.fixture(autouse=True)
def sahte_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    fiyatlar = {"SPY": 100.0, "ABC": 100.0}
    monkeypatch.setattr(fetch, "get_price", lambda s: fiyatlar.get(s))
    monkeypatch.setattr(fetch, "get_earnings_days", lambda s: 40)
    monkeypatch.setattr(
        olcum, "_put_zinciri", lambda s, now=None: zincir_bs({16: 0.38, 30: 0.40, 44: 0.42})
    )


def _v(*gunler: int) -> list[str]:
    return [(NOW.date() + datetime.timedelta(days=g)).isoformat() for g in gunler]


def test_vade_sec_30u_cevreler_ve_sinirli() -> None:
    vadeler = _v(1, 3, 8, 15, 22, 24, 27, 29, 31, 34, 36, 41, 50, 64, 120)
    secilen = vade_sec(vadeler, now=NOW)
    assert _v(29, 31)[0] in secilen and _v(29, 31)[1] in secilen
    assert len(secilen) <= 5
    assert all(7 <= (datetime.date.fromisoformat(v) - NOW.date()).days <= 90 for v in secilen)


def test_vade_sec_bozuk_vade_atlanir() -> None:
    assert vade_sec(["bad", *_v(30)], now=NOW) == _v(30)


def test_okunamayan_sembol_none() -> None:
    assert olc(satir("ZZZ"), "2026-10-23", [], now=NOW) is None


def test_iv30_yoksa_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(olcum, "_put_zinciri", lambda s, now=None: [])
    assert olc(satir("ABC"), "2026-10-23", [], now=NOW) is None


def test_etf_icin_csp_hesaplanmaz() -> None:
    o = olc(satir("SPY", etf=True), "2026-10-23", [], now=NOW)
    assert o is not None and o["csp"] is None
    assert o["kayit"]["iv30"] == pytest.approx(0.40, abs=0.01)
    assert o["kayit"]["sembol"] == "SPY" and o["kayit"]["bilanco_gun"] == 40


def test_hisse_icin_en_iyi_csp_adayi() -> None:
    o = olc(satir("ABC"), "2026-10-23", [], now=NOW)
    assert o is not None and o["csp"] is not None
    assert 2000 <= o["csp"]["sermaye"] <= 15000
    assert 20 <= o["csp"]["dte"] <= 45
    assert o["csp"]["sermaye"] == o["csp"]["strike"] * 100


def test_kanal_parametreleri_paneli_degistirmez() -> None:
    from opsi.params import DEFAULT_PARAMS

    assert olcum.KANAL_PARAMS["filters"]["dte_min"] == 20
    assert olcum.KANAL_PARAMS["filters"]["capital_max"] == 15000.0
    assert DEFAULT_PARAMS["filters"]["dte_min"] == 14


def test_yakin_bilancoda_csp_adayi_yok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch, "get_earnings_days", lambda s: 3)
    o = olc(satir("ABC"), "2026-10-23", [], now=NOW)
    assert o is not None and o["csp"] is None and o["kayit"]["bilanco_gun"] == 3
