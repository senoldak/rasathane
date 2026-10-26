from datetime import date

import pytest

from bioseeder.rasathane.ayar import ayar_oku, hedef_ayristir
from bioseeder.rasathane.olay import Olay, OlayTuru, buyuk_mu, sirala
from bioseeder.rasathane.takvim import (
    TakvimHatasi,
    edgar_acik_mi,
    is_gunleri,
    is_gunu_mu,
    onceki_is_gunu,
)


def _olay(tur, ticker="AAA", faz3=False):
    return Olay(kimlik=f"{ticker}:{tur.name}", tur=tur, ticker=ticker, satir="", ayrinti="",
                tarih=date(2026, 10, 23), faz3=faz3)


def test_buyuk_mu():
    assert buyuk_mu(_olay(OlayTuru.FAZ3_SONUC))
    assert buyuk_mu(_olay(OlayTuru.FDA_ONAY))
    assert buyuk_mu(_olay(OlayTuru.FDA_RET))
    assert not buyuk_mu(_olay(OlayTuru.DURDURULDU, faz3=False))
    assert buyuk_mu(_olay(OlayTuru.DURDURULDU, faz3=True))
    assert not buyuk_mu(_olay(OlayTuru.TARIH_KAYDI))


def test_sirala():
    yeni = _olay(OlayTuru.YENI_FAZ2, "BBB")
    faz2 = _olay(OlayTuru.FAZ2_SONUC, "CCC")
    durdu = _olay(OlayTuru.DURDURULDU, "DDD", faz3=True)
    onay = _olay(OlayTuru.FDA_ONAY, "EEE")
    ret = _olay(OlayTuru.FDA_RET, "FFF")
    sirali = sirala([yeni, faz2, onay, durdu, ret])
    assert sirali.index(durdu) < sirali.index(yeni)
    assert sirali.index(durdu) < sirali.index(faz2)
    assert sirali.index(ret) < sirali.index(onay)


def test_is_gunu():
    assert not is_gunu_mu(date(2026, 10, 24))  # Cumartesi
    assert is_gunu_mu(date(2026, 10, 23))
    assert is_gunu_mu(date(2026, 11, 11))  # Veterans Day: hafta içi, ClinicalTrials.gov çalışır
    assert onceki_is_gunu(date(2026, 10, 26)) == date(2026, 10, 23)
    assert is_gunleri(date(2026, 10, 23), date(2026, 10, 27)) == [
        date(2026, 10, 23), date(2026, 10, 26), date(2026, 10, 27)]


def test_edgar_federal_tatil():
    assert not edgar_acik_mi(date(2026, 11, 11))  # Veterans Day: NYSE açık, EDGAR kapalı
    assert not edgar_acik_mi(date(2026, 10, 12))  # Columbus Day
    assert not edgar_acik_mi(date(2026, 11, 26))
    assert edgar_acik_mi(date(2026, 4, 3))  # Good Friday: NYSE kapalı, SEC açık
    assert not edgar_acik_mi(date(2026, 10, 24))


def test_bilinmeyen_yil_hata():
    with pytest.raises(TakvimHatasi):
        is_gunu_mu(date(2028, 3, 1))


def test_hedef_ayristir():
    assert hedef_ayristir("@rasathane:42") == ("@rasathane", 42)
    assert hedef_ayristir("@kanal") == ("@kanal", None)
    assert hedef_ayristir("-100123:7") == ("-100123", 7)


@pytest.mark.parametrize("deger,beklenen", [
    ("acik", True), ("ACIK ", True), ("kapali", False), (None, False), ("", False),
])
def test_gonderim_acik(deger, beklenen):
    env = {} if deger is None else {"RASATHANE_GONDERIM": deger}
    assert ayar_oku(env).gonderim_acik is beklenen


def test_sec_ua():
    assert ayar_oku({"SEC_ILETISIM": " ad@alan.com "}).sec_ua == "biOF Rasathane ad@alan.com"
    assert ayar_oku({}).sec_ua is None
