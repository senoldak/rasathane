import csv

import pytest

from rasathane_ortak import tek_gonderim as tg
from rasathane_ortak.tek_gonderim import Giden, GonderimHatasi, GonderimKaydi

TOKEN = "123:GIZLI"


class SahteIstek:
    """Yanıtları sırayla döner, çağrıları kaydeder."""

    def __init__(self, *yanitlar):
        self.yanitlar = list(yanitlar)
        self.cagrilar = []
        self.sayac = 100

    def __call__(self, url, alanlar, dosyalar):
        self.cagrilar.append((url, dict(alanlar), dict(dosyalar)))
        if self.yanitlar:
            return self.yanitlar.pop(0)
        self.sayac += 1
        return 200, {"ok": True, "result": {"message_id": self.sayac}}


class SahteUyku:
    def __init__(self):
        self.sureler = []

    def __call__(self, s):
        self.sureler.append(s)


def _gidenler(n=3):
    return [Giden(kart=f"k{i}", sayfa=1, png=b"png%d" % i, aciklama=f"A{i}") for i in range(n)]


def test_hedef_coz():
    assert tg.hedef_coz("@rasathane:5") == ("@rasathane", 5)
    assert tg.hedef_coz("-100123") == ("-100123", None)
    with pytest.raises(ValueError):
        tg.hedef_coz("@grup:abc")


def test_tek_foto_alanlari():
    istek = SahteIstek((200, {"ok": True, "result": {"message_id": 42}}))
    mid = tg.foto_gonder(istek, TOKEN, "@rasathane:5", b"PNG", "INseeder · İçeriden Alımlar · 23.10.2026",
                         uyku=SahteUyku())
    assert mid == 42
    url, alanlar, dosyalar = istek.cagrilar[0]
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    assert alanlar == {"chat_id": "@rasathane", "message_thread_id": "5",
                       "caption": "INseeder · İçeriden Alımlar · 23.10.2026"}
    assert dosyalar["photo"][1] == b"PNG"


def test_429_bekleyip_tekrar():
    uyku = SahteUyku()
    istek = SahteIstek((429, {"ok": False, "parameters": {"retry_after": 3}}),
                       (200, {"ok": True, "result": {"message_id": 7}}))
    assert tg.foto_gonder(istek, TOKEN, "@r:1", b"x", "a", uyku=uyku) == 7
    assert uyku.sureler == [3]


def test_uzun_retry_after_kalici_hata():
    uyku = SahteUyku()
    istek = SahteIstek((429, {"ok": False, "parameters": {"retry_after": 500}}))
    with pytest.raises(GonderimHatasi):
        tg.foto_gonder(istek, TOKEN, "@r:1", b"x", "a", uyku=uyku, azami_bekleme=120)
    assert uyku.sureler == []


def test_ucuncu_429_kalici_hata():
    yanit = (429, {"ok": False, "parameters": {"retry_after": 1}})
    with pytest.raises(GonderimHatasi):
        tg.foto_gonder(SahteIstek(yanit, yanit, yanit, yanit), TOKEN, "@r:1", b"x", "a", uyku=SahteUyku())


def test_kalici_hata():
    istek = SahteIstek((400, {"ok": False, "description": "Bad Request: TOPIC_CLOSED"}))
    with pytest.raises(GonderimHatasi) as e:
        tg.foto_gonder(istek, TOKEN, "@r:1", b"x", "a", uyku=SahteUyku())
    assert "TOPIC_CLOSED" in str(e.value)
    assert TOKEN not in str(e.value)


def test_istek_istisnasi_tokeni_sizdirmaz():
    def bozuk(url, alanlar, dosyalar):
        raise ConnectionError(f"bağlanamadı: {url}")

    with pytest.raises(GonderimHatasi) as e:
        tg.foto_gonder(bozuk, TOKEN, "@r:1", b"x", "a", uyku=SahteUyku())
    assert TOKEN not in str(e.value)


def test_sirayla_sira_ve_kayit(tmp_path):
    yol = tmp_path / "gonderilen_kartlar.csv"
    istek, uyku = SahteIstek(), SahteUyku()
    ids = tg.sirayla_gonder(istek, TOKEN, "@r:5", "2026-10-23", _gidenler(), GonderimKaydi(yol), uyku=uyku)
    assert ids == [101, 102, 103]
    assert [c[1]["caption"] for c in istek.cagrilar] == ["A0", "A1", "A2"]
    with open(yol, encoding="utf-8", newline="") as f:
        satirlar = list(csv.DictReader(f))
    assert [(s["gun"], s["kart"], s["sayfa"], s["mesaj_id"]) for s in satirlar] == [
        ("2026-10-23", "k0", "1", "101"), ("2026-10-23", "k1", "1", "102"), ("2026-10-23", "k2", "1", "103")]
    assert uyku.sureler == [1.5, 1.5]


def test_yarida_kalan_kosu_kaldigi_yerden(tmp_path):
    yol = tmp_path / "gonderilen_kartlar.csv"
    istek = SahteIstek((200, {"ok": True, "result": {"message_id": 1}}),
                       (400, {"ok": False, "description": "Bad Request: chat not found"}))
    with pytest.raises(GonderimHatasi):
        tg.sirayla_gonder(istek, TOKEN, "@r:5", "2026-10-23", _gidenler(), GonderimKaydi(yol), uyku=SahteUyku())
    assert len(istek.cagrilar) == 2
    kayit = GonderimKaydi(yol)
    assert kayit.gonderildi_mi("2026-10-23", "k0", 1)
    assert not kayit.gonderildi_mi("2026-10-23", "k1", 1)

    ikinci = SahteIstek()
    tg.sirayla_gonder(ikinci, TOKEN, "@r:5", "2026-10-23", _gidenler(), GonderimKaydi(yol), uyku=SahteUyku())
    assert [c[1]["caption"] for c in ikinci.cagrilar] == ["A1", "A2"]


def test_sonrasi_her_karttan_sonra(tmp_path):
    yol = tmp_path / "k.csv"
    gorulen = []

    def sonrasi(giden, mid):
        assert GonderimKaydi(yol).gonderildi_mi("g", giden.kart, giden.sayfa)
        gorulen.append((giden.kart, mid))

    istek = SahteIstek((200, {"ok": True, "result": {"message_id": 5}}),
                       (400, {"ok": False, "description": "hata"}))
    with pytest.raises(GonderimHatasi):
        tg.sirayla_gonder(istek, TOKEN, "@r:5", "g", _gidenler(), GonderimKaydi(yol), uyku=SahteUyku(),
                          sonrasi=sonrasi)
    assert gorulen == [("k0", 5)]
