"""Kanal evreni: saf seçim ve CSV okuma."""

from pathlib import Path

from opsi.kanal.evren import evren_oku, evren_sec


def test_evren_sec_ucuzlari_atar_oiye_gore_siralar() -> None:
    a = {"A": (50.0, 10), "B": (1.5, 999), "C": (20.0, 500)}
    assert evren_sec(a, adet=2) == ["C", "A"]


def test_evren_sec_adet_siniri() -> None:
    a = {f"S{i}": (10.0, i) for i in range(300)}
    s = evren_sec(a)
    assert len(s) == 185 and s[0] == "S299"


def test_evren_oku_etf_bool(tmp_path: Path) -> None:
    y = tmp_path / "e.csv"
    y.write_text('sembol,ad,etf\nSPY,SPDR S&P 500,1\nAAPL,"Apple, Inc.",0\n', encoding="utf-8")
    assert evren_oku(y) == [
        {"sembol": "SPY", "ad": "SPDR S&P 500", "etf": True},
        {"sembol": "AAPL", "ad": "Apple, Inc.", "etf": False},
    ]
