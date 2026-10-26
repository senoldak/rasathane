import datetime

from capitolseeder.kanal.arsiv import (
    beyanlari_oku,
    beyanlari_yaz,
    gonderildi_mi,
    gonderim_ekle,
    yenileri_ayir,
)
from tests.kanal.yardimci import beyan


def test_gidis_donus(tmp_path):
    b = [
        beyan(id="x", ilk_gorulme="baslangic", varlik="Şirket, İnc. \"A\""),
        beyan(id="y", ilk_gorulme="2026-10-24", gec=True, tutar_ust=0),
    ]
    beyanlari_yaz(tmp_path / "alt" / "b.csv", b)
    assert beyanlari_oku(tmp_path / "alt" / "b.csv") == b


def test_dosya_yoksa_bos(tmp_path):
    assert beyanlari_oku(tmp_path / "yok.csv") == []


def test_yeniler():
    assert [b.id for b in yenileri_ayir([beyan(id="a"), beyan(id="b")], [beyan(id="a")])] == ["b"]


def test_gonderim_kaydi(tmp_path):
    y = tmp_path / "g.csv"
    assert not gonderildi_mi(y, datetime.date(2026, 10, 24))
    gonderim_ekle(y, datetime.date(2026, 10, 24), ["gunluk", "haftalik"], 55)
    gonderim_ekle(y, datetime.date(2026, 10, 25), ["gunluk"], 56)
    assert gonderildi_mi(y, datetime.date(2026, 10, 24))
    assert not gonderildi_mi(y, datetime.date(2026, 10, 23))
    assert y.read_text(encoding="utf-8").splitlines()[1] == "2026-10-24,gunluk|haftalik,55"
