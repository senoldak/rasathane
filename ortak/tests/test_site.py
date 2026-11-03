import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz, seri_cok_yaz, seri_yaz

ZAMAN = datetime(2026, 11, 3, 23, 30, tzinfo=timezone.utc)
KAYNAKLAR = [Kaynak("Yahoo Finance", "https://finance.yahoo.com/")]
SUTUNLAR = [Sutun("ad", "Emtia", "metin"), Sutun("gunluk", "Günlük", "yuzde", 1)]


def _yaz(kok: Path, satirlar, bolum="emtia", sayfa="pano", sutunlar=SUTUNLAR) -> Path:
    return sayfa_yaz(
        kok,
        bolum,
        sayfa,
        baslik="Emtia Panosu",
        aciklama="a",
        guncellendi=ZAMAN,
        kaynaklar=KAYNAKLAR,
        sutunlar=sutunlar,
        satirlar=satirlar,
    )


def test_sayfa_yaz_bicim(tmp_path: Path) -> None:
    yol = _yaz(tmp_path, [{"ad": "Altın", "gunluk": 0.012, "seri": "GC=F"}])
    assert yol == tmp_path / "emtia" / "pano.json"
    d = json.loads(yol.read_text("utf-8"))
    assert d["sema"] == 1 and d["guncellendi"] == "2026-11-03T23:30:00Z"
    assert d["satirlar"][0]["seri"] == "GC=F" and d["grafik"] == "cizgi"
    assert d["kaynaklar"] == [
        {"ad": "Yahoo Finance", "url": "https://finance.yahoo.com/"}
    ]
    assert d["sutunlar"][1] == {
        "anahtar": "gunluk",
        "baslik": "Günlük",
        "tur": "yuzde",
        "basamak": 1,
    }
    assert "Altın" in yol.read_text("utf-8")
    assert not list(yol.parent.glob("*.tmp"))


def test_nan_ve_none_null_olur(tmp_path: Path) -> None:
    yol = _yaz(
        tmp_path,
        [
            {"ad": "X", "gunluk": float("nan")},
            {"ad": "Y", "gunluk": None},
            {"ad": "Z", "gunluk": float("inf")},
        ],
    )
    metin = yol.read_text("utf-8")
    assert "NaN" not in metin and "Infinity" not in metin
    assert [s["gunluk"] for s in json.loads(metin)["satirlar"]] == [None, None, None]


def test_sutunda_olmayan_anahtar_reddedilir(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _yaz(tmp_path, [{"ad": "X", "fazla": 1}])


def test_gecersiz_bolum_adi(tmp_path: Path) -> None:
    for kotu in ("../x", "Emtia", "a b", "", "a" * 41):
        with pytest.raises(ValueError):
            _yaz(tmp_path, [], bolum=kotu)
    with pytest.raises(ValueError):
        _yaz(tmp_path, [], sayfa="../pano")


def test_seri_yaz(tmp_path: Path) -> None:
    yol = seri_yaz(
        tmp_path,
        "emtia",
        "GC=F",
        [(date(2026, 11, 2), 2701.5), (date(2026, 11, 3), float("nan"))],
        ad="Altın",
        birim="$/ons",
        isaretler=[(date(2026, 11, 3), "52 hafta zirvesi")],
    )
    assert yol == tmp_path / "emtia" / "seri" / "GC=F.json"
    d = json.loads(yol.read_text("utf-8"))
    assert d["sema"] == 1 and d["ad"] == "Altın" and d["birim"] == "$/ons"
    assert d["noktalar"] == [["2026-11-02", 2701.5]]
    assert d["isaretler"] == [["2026-11-03", "52 hafta zirvesi"]]


def test_gecersiz_seri_anahtari(tmp_path: Path) -> None:
    for kotu in ("..", "../x", "a/b", "", "a b", "a" * 41):
        with pytest.raises(ValueError):
            seri_yaz(tmp_path, "emtia", kotu, [], ad="x", birim="y")


def test_seri_cok_yaz_bicim(tmp_path: Path) -> None:
    tarihler = [date(2026, 11, 2), date(2026, 11, 3)]
    yol = seri_cok_yaz(
        tmp_path,
        "grafix",
        "AAPL",
        tarihler,
        {"kapanis": [201.5, float("nan")], "ema233": [None, 199.25]},
        ad="Apple",
        birim="$",
        isaretler=[(date(2026, 11, 3), "Düşen Trend Kırılımı")],
    )
    assert yol == tmp_path / "grafix" / "seri" / "AAPL.json"
    d = json.loads(yol.read_text("utf-8"))
    assert d["tarihler"] == ["2026-11-02", "2026-11-03"]
    assert d["sutunlar"]["kapanis"] == [201.5, None]
    assert d["sutunlar"]["ema233"] == [None, 199.25]
    assert d["isaretler"] == [["2026-11-03", "Düşen Trend Kırılımı"]]
    assert "NaN" not in yol.read_text("utf-8")


def test_seri_cok_uzunluk_uyusmazligi(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        seri_cok_yaz(
            tmp_path,
            "grafix",
            "AAPL",
            [date(2026, 11, 3)],
            {"kapanis": [1.0, 2.0]},
            ad="x",
            birim="$",
        )


def test_seri_cok_gecersiz_sutun_adi(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        seri_cok_yaz(
            tmp_path,
            "grafix",
            "AAPL",
            [date(2026, 11, 3)],
            {"EMA 233": [1.0]},
            ad="x",
            birim="$",
        )
