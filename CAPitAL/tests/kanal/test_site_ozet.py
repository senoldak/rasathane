import datetime
import json
import re

from capitolseeder.kanal.site_ozet import (
    fiyat_ihtiyaci,
    gecikme_ozeti,
    gunluk_ozeti,
    haftalik_ozeti,
    performans_ozeti,
    yaz,
)
from tests.kanal.yardimci import beyan

SIMDI = datetime.datetime(2026, 11, 2, 12, 0, tzinfo=datetime.timezone.utc)
BUGUN = SIMDI.date()
YASAKLI = re.compile(r"\b(al|sat|sinyal|öneri|fırsat)\b", re.IGNORECASE)


def _seri(bas, bit, a, b):
    gunler = (bas + datetime.timedelta(days=i) for i in range((bit - bas).days + 1))
    gunler = list(gunler)
    n = len(gunler) - 1
    return [(g, a + (b - a) * i / n) for i, g in enumerate(gunler)]


def _fiyatlar():
    bas, bit = datetime.date(2026, 8, 20), BUGUN
    return {
        "AAA": _seri(bas, bit, 100, 120),
        "BBB": _seri(bas, bit, 100, 110),
        "CCC": _seri(bas, bit, 100, 90),
        "SPY": _seri(bas, bit, 100, 105),
    }


def _veri():
    """Üç hissede alımlar; üye Bir AAA'da beş alım yapmış (performans için yeterli)."""
    return _alimlar("Üye Bir", 5, "AAA") + _alimlar("Üye İki", 3, "BBB") + _alimlar("Üye Üç", 3, "CCC")


def _alimlar(uye="Üye Bir", sayi=5, ticker="AAA"):
    return [
        beyan(
            id=f"{uye}-{i}",
            uye=uye,
            ticker=ticker,
            islem="Purchase",
            islem_tarihi=datetime.date(2026, 9, 1) + datetime.timedelta(days=i),
            beyan_tarihi=datetime.date(2026, 10, 1),
            gecikme=30,
        )
        for i in range(sayi)
    ]


def _oku(yol):
    return json.loads(yol.read_text(encoding="utf-8"))


def test_gunluk_son_gun_en_buyuk_ve_uye_siniri():
    son = datetime.date(2026, 10, 30)
    b = [beyan(id=f"x{i}", uye="Üye Üç", ticker=f"T{i}", tutar_alt=1000 * i, beyan_tarihi=son) for i in range(5)]
    b.append(beyan(id="eski", beyan_tarihi=datetime.date(2026, 10, 1)))
    ozet = gunluk_ozeti(b)
    assert ozet["tarih"] == "2026-10-30"
    assert ozet["toplam"] == 5 and ozet["uye"] == 1
    assert len(ozet["satirlar"]) == 3  # üye başı en çok üç
    assert ozet["satirlar"][0]["ticker"] == "T4"  # en büyük tutar önde


def test_gunluk_hisse_yoksa_none():
    assert gunluk_ozeti([beyan(id="t", varlik_turu="", ticker="")]) is None


def test_haftalik_pazartesi_cuma_ve_taraflar():
    b = [
        beyan(id="a1", uye="A", ticker="AAA", parti="D", beyan_tarihi=datetime.date(2026, 10, 27)),
        beyan(id="a2", uye="B", ticker="AAA", parti="R", beyan_tarihi=datetime.date(2026, 10, 28)),
        beyan(id="b1", uye="C", ticker="BBB", parti="D", beyan_tarihi=datetime.date(2026, 10, 28)),
        beyan(id="c1", uye="D", ticker="CCC", parti="R", beyan_tarihi=datetime.date(2026, 10, 29), islem="Sale (Full)"),
    ]
    ozet = haftalik_ozeti(b)
    assert ozet["baslangic"] == "2026-10-26" and ozet["bitis"] == "2026-10-30"
    ilk = ozet["satirlar"][0]
    assert ilk["ticker"] == "AAA" and ilk["alan"] == 2 and ilk["iki_parti"] is True
    assert {s["ticker"] for s in ozet["satirlar"]} == {"AAA", "BBB", "CCC"}


def test_haftalik_az_hisse_yoksa_none():
    assert haftalik_ozeti(_alimlar(sayi=5)) is None  # tek hisse, üç şartı sağlanmaz


def test_performans_fark_ve_siralama():
    ozet = performans_ozeti(_alimlar("Üye Bir", 5, "AAA") + _alimlar("Üye İki", 5, "AAA"), _fiyatlar(), BUGUN)
    en = ozet["en_yuksek"][0]
    assert en["uye"] == "Üye Bir" and en["alim"] == 5
    assert en["ort_degisim"] > en["ort_spy"]
    assert en["fark"] > 0


def test_performans_spy_yoksa_atlanir():
    assert performans_ozeti(_alimlar(), {"AAA": _seri(datetime.date(2026, 8, 20), BUGUN, 100, 120)}, BUGUN) is None


def test_gecikme_seri_hizali_ve_ilk_degerde_olcekli():
    b = [beyan(id="g", uye="Üye Bir", ticker="AAA", islem="Purchase", beyan_tarihi=datetime.date(2026, 10, 30),
               islem_tarihi=datetime.date(2026, 9, 1), gecikme=30)]
    ozet = gecikme_ozeti(b, _fiyatlar(), BUGUN)
    assert ozet["ticker"] == "AAA" and ozet["gecikme"] == 30
    assert len(ozet["tarihler"]) == len(ozet["hisse"]) == len(ozet["spy"]) > 2
    assert abs(ozet["spy"][0] - ozet["hisse"][0]) < 1e-6


def test_fiyat_ihtiyaci_semboller_ve_spy():
    semboller, bas = fiyat_ihtiyaci(_alimlar(), BUGUN)
    assert {"AAA", "SPY"} <= semboller
    assert bas <= datetime.date(2026, 9, 1)


def test_yaz_dosyalar_ve_seri_klasoru(tmp_path):
    yollar = yaz(tmp_path, SIMDI, _veri(), None)
    assert {p.name for p in yollar} == {"ozet-gunluk.json", "ozet-haftalik.json"}
    assert all(p.parent == tmp_path / "capital" / "seri" for p in yollar)
    assert _oku(tmp_path / "capital" / "seri" / "ozet-gunluk.json")["sema"] == 1


def test_yaz_fiyatlarla_dort_bolum(tmp_path):
    yollar = yaz(tmp_path, SIMDI, _veri(), _fiyatlar())
    adlar = {p.name for p in yollar}
    assert {"ozet-gunluk.json", "ozet-haftalik.json", "ozet-performans.json", "ozet-gecikme.json"} <= adlar


def test_yaz_bos_beyan_hicbir_sey_yazmaz(tmp_path):
    assert yaz(tmp_path, SIMDI, [], None) == []
    assert not (tmp_path / "capital").exists()


def test_metinde_yasakli_sozcuk_yok(tmp_path):
    yaz(tmp_path, SIMDI, _veri(), _fiyatlar())
    metin = " ".join(
        (tmp_path / "capital" / "seri" / f"ozet-{a}.json").read_text(encoding="utf-8")
        for a in ("gunluk", "haftalik", "performans", "gecikme")
    )
    # Alış ve Satış beyan türü olarak geçebilir; yalnız yasak sözcükler aranır.
    kalan = [m for m in YASAKLI.findall(metin) if m.lower() not in {"alış", "satış"}]
    assert kalan == []


def test_hisse_dosyalari_fiyatli_kodlar(tmp_path):
    b = _veri() + [beyan(id="yok", uye="Üye Dört", ticker="ZZZ", islem="Purchase")]
    fiyat = _fiyatlar()
    yollar = yaz(tmp_path, SIMDI, b, fiyat)
    adlar = {p.name for p in yollar}
    assert {"hisse-AAA.json", "hisse-BBB.json", "hisse-CCC.json"} <= adlar
    assert "hisse-ZZZ.json" not in adlar  # fiyatı yok, dosya da yok
    veri = _oku(tmp_path / "capital" / "seri" / "hisse-AAA.json")
    assert veri["ticker"] == "AAA" and len(veri["tarihler"]) == len(veri["kapanis"]) > 2
