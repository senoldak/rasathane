import datetime

from rasathane_emtia.merkez_altin import TROY_ONS_TON, ayikla, ton_cevir

ORNEK = """<message:StructureSpecificData><message:DataSet>
<Series COUNTRY="TUR" INDICATOR="GOLD35P_REVS" UNIT="XDR" FREQUENCY="M"/>
<Obs TIME_PERIOD="2026-M02" OBS_VALUE="700000000" DERIVATION_TYPE="O"/>
<Obs TIME_PERIOD="2026-M01" OBS_VALUE="350000000" DERIVATION_TYPE="O"/>
</Series>
</message:DataSet></message:StructureSpecificData>"""


def test_ton_cevrimi_35_sdr_ons() -> None:
    assert abs(ton_cevir(35 * TROY_ONS_TON) - 1.0) < 1e-9


def test_ayikla_tarih_sirasi_ve_ton() -> None:
    seriler = ayikla(ORNEK)
    tur = seriler["TUR"]
    assert [d for d, _ in tur] == [datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)]
    assert tur[0][1] < tur[1][1]
