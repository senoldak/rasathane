"""Kanal kart verisi: saf fonksiyonlar."""

import pytest

from opsi.kanal.gecmis import Kayit
from opsi.kanal.kartlar import asagi_yon_primi, csp_kartlari, iv_sarsintisi
from opsi.kanal.olcum import CspAday

ADLAR = {f"S{i}": f"Sirket {i}" for i in range(20)} | {"MRNA": "Moderna"}


def kayit(tarih: str, sembol: str, **k: object) -> Kayit:
    base: dict[str, object] = {
        "tarih": tarih,
        "sembol": sembol,
        "kapanis": 10.0,
        "iv30": 0.5,
        "skew25": 1.1,
        "atm_iv": 0.5,
        "bilanco_gun": 40,
    }
    base.update(k)
    return base  # type: ignore[return-value]


def onceki10() -> list[Kayit]:
    return [kayit("2026-10-22", f"S{i}", iv30=0.50, kapanis=10.0) for i in range(10)]


def bugun10() -> list[Kayit]:
    # S0..S9 değişimleri: -45%, -35%, ..., +45%
    return [
        kayit("2026-10-23", f"S{i}", iv30=0.50 * (1 + (i - 4.5) / 10), kapanis=11.0)
        for i in range(10)
    ]


def aday(sembol: str, sermaye: float, skor: float = 60.0) -> CspAday:
    return {"sembol": sembol, "skor": skor, "strike": sermaye / 100, "dte": 30, "sermaye": sermaye}


def test_sarsinti_4_dusen_4_yukselen_sirali() -> None:
    s = iv_sarsintisi(bugun10(), onceki10(), ADLAR, bosluk_gun=1)
    assert s is not None
    assert [r["iv_degisim"] < 0 for r in s] == [True] * 4 + [False] * 4
    assert s[0]["sembol"] == "S0" and s[3]["sembol"] == "S3"
    assert s[4]["sembol"] == "S9" and s[7]["sembol"] == "S6"
    assert s[0]["fiyat_degisim"] == pytest.approx(0.10)
    assert s[0]["ad"] == "Sirket 0"


def test_sarsinti_bes_gunden_eski_karsilastirma_yok() -> None:
    assert iv_sarsintisi(bugun10(), onceki10(), ADLAR, bosluk_gun=6) is None


def test_sarsinti_bir_gunde_eksik_sembol_atlanir() -> None:
    bugun = bugun10() + [kayit("2026-10-23", "S15", iv30=0.9)]
    once = onceki10() + [kayit("2026-10-22", "S16", iv30=0.9)]
    s = iv_sarsintisi(bugun, once, ADLAR, 1)
    assert s is not None and {r["sembol"] for r in s}.isdisjoint({"S15", "S16"})


def test_sarsinti_bilanco_isareti_arada_aciklanan() -> None:
    once = onceki10() + [kayit("2026-10-22", "MRNA", iv30=1.09, bilanco_gun=1)]
    simdi = bugun10() + [kayit("2026-10-23", "MRNA", iv30=0.40, bilanco_gun=90)]
    s = iv_sarsintisi(simdi, once, ADLAR, 1)
    assert s is not None
    r = [x for x in s if x["sembol"] == "MRNA"]
    assert r and r[0]["bilanco"] is True
    assert not next(x for x in s if x["sembol"] == "S0")["bilanco"]


def test_sarsinti_yaklasan_bilanco_isareti() -> None:
    simdi = bugun10()
    simdi[0] = kayit("2026-10-23", "S0", iv30=0.25, kapanis=11.0, bilanco_gun=3)
    s = iv_sarsintisi(simdi, onceki10(), ADLAR, 1)
    assert s is not None and s[0]["bilanco"] is True


def test_sarsinti_az_sembolde_none() -> None:
    assert iv_sarsintisi(bugun10()[:5], onceki10()[:5], ADLAR, 1) is None


def test_prim_fark_medyana_gore() -> None:
    k = asagi_yon_primi([kayit("t", f"S{i}", skew25=1.0 + i / 10) for i in range(9)], ADLAR)
    assert k is not None
    assert k["medyan"] == pytest.approx(1.4)
    assert len(k["satirlar"]) == 6 and k["satirlar"][0]["sembol"] == "S8"
    assert k["satirlar"][0]["fark"] == pytest.approx(0.4)
    assert len(k["tum_skewler"]) == 9


def test_prim_alti_skewden_az_none() -> None:
    assert asagi_yon_primi([kayit("t", f"S{i}") for i in range(5)], ADLAR) is None


def test_csp_ucten_az_aday_bandi_atlanir() -> None:
    bugun = [kayit("2026-10-23", s) for s in "ABC"]
    assert csp_kartlari([aday("A", 3000), aday("B", 4000), aday("C", 8000)], bugun, bugun, {}) == []


def test_csp_bant_ilk_bes_skora_gore() -> None:
    semboller = [f"S{i}" for i in range(7)]
    bugun = [kayit("2026-10-23", s, kapanis=40.0, iv30=0.4) for s in semboller]
    adaylar = [aday(s, 3000 + i, skor=50 + i) for i, s in enumerate(semboller)]
    kartlar = csp_kartlari(adaylar, bugun, bugun, ADLAR)
    assert len(kartlar) == 1 and kartlar[0]["bant"] == "$2k–5k"
    satirlar = kartlar[0]["satirlar"]
    assert [r["sembol"] for r in satirlar] == ["S6", "S5", "S4", "S3", "S2"]
    assert satirlar[0]["hareket_alt"] < 40.0 < satirlar[0]["hareket_ust"]
    assert kartlar[0]["iv_etiket"] == "IV yüzd. (23.10'dan beri)"


def test_csp_15000_ust_siniri_dahil() -> None:
    semboller = [f"S{i}" for i in range(3)]
    bugun = [kayit("2026-10-23", s) for s in semboller]
    kartlar = csp_kartlari([aday(s, 15000.0) for s in semboller], bugun, bugun, ADLAR)
    assert len(kartlar) == 1 and kartlar[0]["bant"] == "$5k–15k"


def test_csp_kisa_gecmiste_iv_konum_bos() -> None:
    semboller = [f"S{i}" for i in range(3)]
    bugun = [kayit("2026-10-23", s) for s in semboller]
    kartlar = csp_kartlari([aday(s, 3000.0) for s in semboller], bugun, bugun, ADLAR)
    assert all(r["iv_konum"] is None for r in kartlar[0]["satirlar"])


def test_csp_yeterli_gecmiste_iv_konum_dolu() -> None:
    gecmis = [
        kayit(f"2026-09-{g:02d}", f"S{i}", iv30=0.3 + g / 100)
        for g in range(1, 26)
        for i in range(3)
    ]
    bugun = [kayit("2026-10-23", f"S{i}", iv30=0.9) for i in range(3)]
    kartlar = csp_kartlari([aday(f"S{i}", 3000.0) for i in range(3)], bugun, gecmis, ADLAR)
    assert all(r["iv_konum"] == 1.0 for r in kartlar[0]["satirlar"])
