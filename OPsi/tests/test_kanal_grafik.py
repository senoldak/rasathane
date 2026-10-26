"""OPsi Oynaklık grafiği: seçim, gerçekleşen oynaklık ve kart alanları."""

import datetime
import math

from opsi.kanal.gecmis import Kayit
from opsi.kanal.grafik import gerceklesen_oynaklik, oynaklik_grafigi, oynaklik_secimi
from opsi.kanal.kartlar import PrimKarti, SarsintiSatiri

PRIM: PrimKarti = {
    "satirlar": [{"sembol": "ECHO", "ad": "EchoStar", "kapanis": 89.0, "skew": 1.21, "fark": 0.19}],
    "medyan": 1.02,
    "tum_skewler": [1.0, 1.2],
}
SARSINTI: list[SarsintiSatiri] = [
    {
        "sembol": "XEL",
        "ad": "Xcel",
        "kapanis": 78.0,
        "fiyat_degisim": 0.01,
        "iv_once": 0.2,
        "iv_simdi": 0.3,
        "iv_degisim": 0.5,
        "bilanco": False,
    }
]


def test_secim_prim_once() -> None:
    assert oynaklik_secimi(PRIM, SARSINTI) == ("ECHO", "aşağı yön primi en yüksek")
    assert oynaklik_secimi(None, SARSINTI) == ("XEL", "IV sarsıntısı en sert")
    assert oynaklik_secimi(None, None) is None


def test_gerceklesen_oynaklik() -> None:
    sabit = [100 * 1.01**i for i in range(40)]
    rv = gerceklesen_oynaklik(sabit)
    assert len(rv) == 20 and max(rv) < 1e-9
    dalgali = [100 * (1.02 if i % 2 else 0.98) for i in range(41)]
    beklenen = math.sqrt(252) * math.log(1.02 / 0.98)  # gidip gelen fiyatın günlük log getirisi
    assert abs(gerceklesen_oynaklik(dalgali)[-1] - beklenen) / beklenen < 0.05


def test_grafik_alanlari() -> None:
    bugun = datetime.date(2026, 10, 23)
    fiyatlar = [
        ((bugun - datetime.timedelta(days=140 - i)).isoformat(), 100 + (i % 4)) for i in range(141)
    ]
    kayit: Kayit = {
        "tarih": "2026-10-23",
        "sembol": "ECHO",
        "kapanis": 89.0,
        "iv30": 0.312,
        "skew25": 1.21,
        "atm_iv": 0.3,
        "bilanco_gun": 12,
    }
    g = oynaklik_grafigi(
        "ECHO", "EchoStar", "aşağı yön primi en yüksek", "2026-10-23", kayit, fiyatlar
    )
    assert (g.fikir, g.tarih, g.baslik) == ("OPsi", "23.10.2026", "ECHO · EchoStar")
    assert g.alt_baslik == "aşağı yön primi en yüksek · bilançoya 12 gün"
    assert g.ozet[0][0] == "IV30 bugün" and g.ozet[0][1].vurgu and g.ozet[0][1].metin == "%31,2"
    assert g.yatay == 31.2 and g.yuzde_eksen
    assert g.seri_adi == "gerçekleşen oynaklık (20g)"
    assert g.gunler[-1] == bugun and (bugun - g.gunler[0]).days <= 93
    assert g.kaynak == "Yahoo Finance"


def test_bilanco_bugunse_gun_yazilmaz() -> None:
    bugun = datetime.date(2026, 10, 23)
    fiyatlar = [
        ((bugun - datetime.timedelta(days=140 - i)).isoformat(), 100.0 + (i % 4))
        for i in range(141)
    ]
    kayit: Kayit = {
        "tarih": "2026-10-23",
        "sembol": "VZ",
        "kapanis": 43.0,
        "iv30": 0.25,
        "skew25": 1.1,
        "atm_iv": 0.25,
        "bilanco_gun": 0,
    }
    g = oynaklik_grafigi("VZ", "Verizon", "IV sarsıntısı en sert", "2026-10-23", kayit, fiyatlar)
    assert g.alt_baslik == "IV sarsıntısı en sert · bilanço bugün"
