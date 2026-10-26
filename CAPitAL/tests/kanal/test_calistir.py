import datetime

import pytest

from capitolseeder.kanal.arsiv import beyanlari_oku
from capitolseeder.kanal.calistir import calistir, main
from capitolseeder.kanal.kaynak import VeriHatasi
from capitolseeder.kanal.telegram import GonderimHatasi
from tests.kanal.yardimci import ornek_satir

PERSEMBE = datetime.date(2026, 10, 22)
CUMA = datetime.date(2026, 10, 23)
ORTAM = {"KANAL_GONDER": "1", "TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_SAHIP_ID": "9", "TELEGRAM_HEDEF": "@rasathane:12"}


class Sahte:
    def __init__(self, hata=None, hata_karti=None):
        self.gonderilen = []
        self.bildirilen = []
        self.hata = hata
        self.hata_karti = hata_karti  # verilirse yalnız bu kartta hata

    def gonderici(self, token, hedef, gun, gidenler, kayit):
        ids = []
        for g in gidenler:
            if kayit.gonderildi_mi(gun, g.kart, g.sayfa):
                continue
            if self.hata and (self.hata_karti is None or self.hata_karti == g.kart):
                raise self.hata
            self.gonderilen.append((g.kart, g.aciklama, hedef))
            kayit.ekle(gun, g.kart, g.sayfa, 77)
            ids.append(77)
        return ids

    def kartlar(self):
        return [k for k, _, _ in self.gonderilen]

    def bildirici(self, token, sahip, metin):
        self.bildirilen.append(metin)


def _kaynak(*ekler):
    temel = [ornek_satir(id=f"s{i}", ticker=t, filing_date="2026-10-20")
             for i, t in enumerate(["AAA", "BBB", "CCC"])]
    return temel + list(ekler)


def _calistir(tmp_path, bugun, satirlar, sahte, ortam=ORTAM, kuru=False, hepsi=False, fiyat_cekici=None,
              grafik_fiyat_cekici=None):
    return calistir(
        bugun, kuru, tmp_path / "veri", tmp_path / "cikti", satirlar=satirlar, ortam=ortam,
        gonderici=sahte.gonderici, bildirici=sahte.bildirici, hepsi=hepsi,
        fiyat_cekici=fiyat_cekici or (lambda s, b: {}), grafik_fiyat_cekici=grafik_fiyat_cekici,
    )


def test_ilk_kosu_kart_yok_arsiv_dolar(tmp_path):
    s = Sahte()
    assert _calistir(tmp_path, PERSEMBE, _kaynak(), s) == []
    arsiv = beyanlari_oku(tmp_path / "veri" / "beyanlar.csv")
    assert len(arsiv) == 3 and {b.ilk_gorulme for b in arsiv} == {"baslangic"}
    assert s.gonderilen == [] and not (tmp_path / "veri" / "gonderimler.csv").exists()


def test_ikinci_kosu_gunluk_karti_ve_kayit(tmp_path):
    s = Sahte()
    _calistir(tmp_path, PERSEMBE, _kaynak(), s)
    yeni = [ornek_satir(id="y1", ticker="NEW", filing_date="2026-10-22"),
            ornek_satir(id="y2", ticker="NEW2", filing_date="2026-10-22", filer_name="Ann Other")]
    assert _calistir(tmp_path, PERSEMBE, _kaynak(*yeni), s) == ["gunluk"]
    assert s.kartlar() == ["gunluk"]
    assert s.gonderilen[0][1] == "CAPitAL · Günün Kongre Beyanları · 22.10.2026"
    assert (tmp_path / "cikti" / "2026-10-22_gunluk.png").exists()
    kayit = (tmp_path / "veri" / "gonderimler.csv").read_text(encoding="utf-8").splitlines()
    assert kayit[1] == "2026-10-22,gunluk,77"
    arsiv = beyanlari_oku(tmp_path / "veri" / "beyanlar.csv")
    assert [b.ilk_gorulme for b in arsiv if b.id == "y1"] == ["2026-10-22"]


def test_ayni_gun_ikinci_kosu_gondermez(tmp_path):
    s = Sahte()
    _calistir(tmp_path, PERSEMBE, _kaynak(), s)
    _calistir(tmp_path, PERSEMBE, _kaynak(ornek_satir(id="y1", ticker="NEW")), s)
    once = (tmp_path / "veri" / "beyanlar.csv").read_text(encoding="utf-8")
    assert _calistir(tmp_path, PERSEMBE, _kaynak(ornek_satir(id="y1"), ornek_satir(id="y9")), s) == []
    assert len(s.gonderilen) == 1
    assert (tmp_path / "veri" / "beyanlar.csv").read_text(encoding="utf-8") == once


def test_gonderim_hatasi_arsivi_yazmaz(tmp_path):
    _calistir(tmp_path, PERSEMBE, _kaynak(), Sahte())
    once = (tmp_path / "veri" / "beyanlar.csv").read_text(encoding="utf-8")
    s = Sahte(hata=GonderimHatasi("reddedildi"))
    with pytest.raises(GonderimHatasi):
        _calistir(tmp_path, PERSEMBE, _kaynak(ornek_satir(id="y1", ticker="NEW")), s)
    assert (tmp_path / "veri" / "beyanlar.csv").read_text(encoding="utf-8") == once
    assert not (tmp_path / "veri" / "gonderimler.csv").exists()
    assert s.bildirilen and "reddedildi" in s.bildirilen[0]


def test_main_hata_kodu(tmp_path, monkeypatch):
    import capitolseeder.kanal.calistir as c

    def patla(*a, **k):
        raise VeriHatasi("bozuk")

    monkeypatch.setattr(c, "calistir", patla)
    assert main(["--veri", str(tmp_path), "--cikti", str(tmp_path)]) == 1


def test_bozuk_kaynak_bildirir(tmp_path):
    s = Sahte()
    with pytest.raises(VeriHatasi):
        _calistir(tmp_path, PERSEMBE, [ornek_satir(branch="executive")], s)
    assert s.gonderilen == [] and len(s.bildirilen) == 1
    assert not (tmp_path / "veri" / "beyanlar.csv").exists()


def test_cuma_album_iki_kart(tmp_path):
    s = Sahte()
    _calistir(tmp_path, PERSEMBE, _kaynak(), s)
    yeni = [ornek_satir(id=f"y{i}", ticker=t, filing_date="2026-10-22", filer_name=f"Uye {i}")
            for i, t in enumerate(["NEW", "NEW2", "NEW3"])]
    assert _calistir(tmp_path, CUMA, _kaynak(*yeni), s) == ["gunluk", "haftalik"]
    assert s.kartlar() == ["gunluk", "haftalik"]


def test_yarida_kalinca_arsiv_yazilir_ve_kaldigi_yerden_surer(tmp_path):
    _calistir(tmp_path, PERSEMBE, _kaynak(), Sahte())
    yeni = [ornek_satir(id=f"y{i}", ticker=t, filing_date="2026-10-22", filer_name=f"Uye {i}")
            for i, t in enumerate(["NEW", "NEW2", "NEW3"])]
    s = Sahte(hata=GonderimHatasi("TOPIC_CLOSED"), hata_karti="haftalik")
    with pytest.raises(GonderimHatasi):
        _calistir(tmp_path, CUMA, _kaynak(*yeni), s)
    assert s.kartlar() == ["gunluk"]
    assert {b.id for b in beyanlari_oku(tmp_path / "veri" / "beyanlar.csv")} >= {"y0", "y1", "y2"}
    assert not (tmp_path / "veri" / "gonderimler.csv").exists()
    assert s.bildirilen and "TOPIC_CLOSED" in s.bildirilen[-1]
    ikinci = Sahte()
    _calistir(tmp_path, CUMA, _kaynak(*yeni), ikinci)
    assert ikinci.kartlar() == ["haftalik"]
    assert (tmp_path / "veri" / "gonderimler.csv").exists()


def test_kuru_kayit_ve_arsiv_yazmaz(tmp_path):
    s = Sahte()
    _calistir(tmp_path, PERSEMBE, _kaynak(), s)
    once = (tmp_path / "veri" / "beyanlar.csv").read_text(encoding="utf-8")
    assert _calistir(tmp_path, PERSEMBE, _kaynak(ornek_satir(id="y1", ticker="NEW")), s, kuru=True) == ["gunluk"]
    assert s.gonderilen == [] and not (tmp_path / "veri" / "gonderimler.csv").exists()
    assert (tmp_path / "veri" / "beyanlar.csv").read_text(encoding="utf-8") == once
    # önizleme yeni beyanları "yemez": ardından gelen gerçek koşu onları yine gönderir
    assert _calistir(tmp_path, PERSEMBE, _kaynak(ornek_satir(id="y1", ticker="NEW")), s) == ["gunluk"]


def test_gonder_ayari_yoksa_kuru(tmp_path):
    s = Sahte()
    ortam = {k: v for k, v in ORTAM.items() if k != "KANAL_GONDER"}
    _calistir(tmp_path, PERSEMBE, _kaynak(), s, ortam=ortam)
    _calistir(tmp_path, PERSEMBE, _kaynak(ornek_satir(id="y1", ticker="NEW")), s, ortam=ortam)
    assert s.gonderilen == [] and not (tmp_path / "veri" / "gonderimler.csv").exists()


def test_hepsi_ilk_kosuda_uc_kart(tmp_path):
    s = Sahte()
    alimlar = [ornek_satir(id=f"{u}{i}", filer_name=u, ticker=t, transaction_date="2026-09-01",
                           filing_date="2026-10-20")
               for u, t in (("Ann Up", "UP"), ("Bob Down", "DN")) for i in range(5)]
    satirlar = _kaynak(*alimlar)

    def fiyatlar(semboller, baslangic):
        assert {"UP", "DN"} <= set(semboller)
        g = [datetime.date(2026, 9, 1), datetime.date(2026, 10, 22)]
        f = {t: list(zip(g, [100, 101])) for t in semboller}
        return f | {"SPY": list(zip(g, [100, 105])), "UP": list(zip(g, [100, 120])), "DN": list(zip(g, [100, 90]))}

    adlar = _calistir(tmp_path, PERSEMBE, satirlar, s, kuru=True, hepsi=True, fiyat_cekici=fiyatlar)
    assert adlar == ["gunluk", "haftalik", "performans", "performans_dusuk"]
    assert all((tmp_path / "cikti" / f"2026-10-22_{a}.png").exists() for a in adlar)
    assert s.gonderilen == [] and not (tmp_path / "veri" / "gonderimler.csv").exists()


def test_performans_hatasi_diger_kartlari_durdurmaz(tmp_path):
    s = Sahte()
    adlar = _calistir(tmp_path, PERSEMBE, _kaynak(), s, kuru=True, hepsi=True)
    assert adlar == ["gunluk", "haftalik"] and len(s.bildirilen) == 1


def test_ilk_kosu_gonderim_acikken_de_gondermez(tmp_path):
    s = Sahte()
    ilk_cuma = datetime.date(2026, 11, 6)
    satirlar = [ornek_satir(id=f"s{i}", ticker=t, filing_date="2026-11-02") for i, t in enumerate(["A", "B", "C"])]
    assert _calistir(tmp_path, ilk_cuma, satirlar, s) == []
    assert s.gonderilen == [] and s.bildirilen == []


def test_fiyat_eksikse_bir_kez_daha_dener(tmp_path):
    s = Sahte()
    alimlar = [ornek_satir(id=f"{u}{i}", filer_name=u, ticker=t, transaction_date="2026-09-01",
                           filing_date="2026-10-20")
               for u, t in (("Ann Up", "UP"), ("Bob Down", "DN")) for i in range(5)]
    g = [datetime.date(2026, 9, 1), datetime.date(2026, 10, 22)]
    tam = {t: list(zip(g, [100, 101])) for t in ("AAA", "BBB", "CCC")}
    tam |= {"SPY": list(zip(g, [100, 105])), "UP": list(zip(g, [100, 120])), "DN": list(zip(g, [100, 90]))}
    cagri = []

    def fiyatlar(semboller, baslangic):
        cagri.append(1)
        return tam if len(cagri) > 1 else {"SPY": tam["SPY"]}

    adlar = _calistir(tmp_path, PERSEMBE, _kaynak(*alimlar), s, kuru=True, hepsi=True, fiyat_cekici=fiyatlar)
    assert "performans" in adlar and len(cagri) == 2 and s.bildirilen == []


def test_main_beklenmeyen_hatayi_bildirir(tmp_path, monkeypatch):
    import capitolseeder.kanal.calistir as c

    bildirilen = []
    monkeypatch.setattr(c, "calistir", lambda *a, **k: (_ for _ in ()).throw(KeyError("bozuk csv")))
    monkeypatch.setattr(c, "sahibe_bildir", lambda t, s, m: bildirilen.append(m))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_SAHIP_ID", "9")
    assert main(["--veri", str(tmp_path), "--cikti", str(tmp_path)]) == 1
    assert bildirilen and "bozuk csv" in bildirilen[0]


def test_main_varsayilan_tarih_utc_gunu(tmp_path, monkeypatch):
    import logging

    import capitolseeder.kanal.calistir as c

    class SahteSaat(datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # Perşembe 21:05 UTC = İstanbul'da Cuma 00:05
            return datetime.datetime(2026, 10, 22, 21, 5, tzinfo=datetime.timezone.utc).astimezone(tz)

    gorulen = {}
    monkeypatch.setattr(c.datetime, "datetime", SahteSaat)
    monkeypatch.setattr(c, "calistir", lambda bugun, *a, **k: gorulen.setdefault("bugun", bugun) and [])
    assert main(["--veri", str(tmp_path), "--cikti", str(tmp_path)]) == 0
    assert gorulen["bugun"] == datetime.date(2026, 10, 22)
    assert logging.getLogger("httpx").level == logging.WARNING


def _grafik_fiyatlari(semboller, baslangic):
    gunler = [baslangic + datetime.timedelta(days=i) for i in range(400) if baslangic + datetime.timedelta(days=i) <= CUMA]
    return {t: [(g, 100.0 + i) for i, g in enumerate(gunler)] for t in list(semboller) + ["SPY"]}


def _cuma_yeni():
    return [ornek_satir(id=f"y{i}", ticker=t, filing_date="2026-10-22", filer_name=f"Uye {i}")
            for i, t in enumerate(["NEW", "NEW2", "NEW3"])]


def test_grafik_gunlukten_sonra_haftaliktan_once(tmp_path):
    _calistir(tmp_path, PERSEMBE, _kaynak(), Sahte())
    s = Sahte()
    adlar = _calistir(tmp_path, CUMA, _kaynak(*_cuma_yeni()), s, grafik_fiyat_cekici=_grafik_fiyatlari)
    assert adlar == ["gunluk", "grafik", "haftalik"]
    assert s.kartlar() == ["gunluk", "grafik", "haftalik"]
    assert s.gonderilen[1][1] == "CAPitAL · Beyan Gecikmesi · 23.10.2026"
    assert (tmp_path / "cikti" / "2026-10-23_grafik.png").exists()


def test_grafik_hatasi_gunlugu_durdurmaz(tmp_path):
    _calistir(tmp_path, PERSEMBE, _kaynak(), Sahte())

    def bozuk(semboller, baslangic):
        raise RuntimeError("Yahoo kapalı")

    s = Sahte()
    adlar = _calistir(tmp_path, CUMA, _kaynak(*_cuma_yeni()), s, grafik_fiyat_cekici=bozuk)
    assert adlar == ["gunluk", "haftalik"] and s.kartlar() == ["gunluk", "haftalik"]
    assert any("Yahoo kapalı" in m for m in s.bildirilen)


def test_grafik_gonderilemezse_yeniden_kosuda_gider(tmp_path):
    _calistir(tmp_path, PERSEMBE, _kaynak(), Sahte())
    yeni = [ornek_satir(id="y1", ticker="NEW", filing_date="2026-10-22")]
    s = Sahte(hata=GonderimHatasi("Bad Gateway"), hata_karti="grafik")
    with pytest.raises(GonderimHatasi):
        _calistir(tmp_path, PERSEMBE, _kaynak(*yeni), s, grafik_fiyat_cekici=_grafik_fiyatlari)
    assert s.kartlar() == ["gunluk"]
    ikinci = Sahte()
    assert _calistir(tmp_path, PERSEMBE, _kaynak(*yeni), ikinci, grafik_fiyat_cekici=_grafik_fiyatlari) == [
        "gunluk", "grafik"]
    assert ikinci.kartlar() == ["grafik"]
    assert (tmp_path / "veri" / "gonderimler.csv").exists()
