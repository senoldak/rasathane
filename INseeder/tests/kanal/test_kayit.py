from datetime import date, timedelta

from inseeder.kanal.kayit import Kayit
from tests.kanal.yardimci import beyan

BUGUN = date(2026, 10, 24)


def test_roundtrip(tmp_path):
    k = Kayit(tmp_path)
    b = beyan(sonraki_pay=None)
    b2 = beyan(kod="S", tutar=6e6)
    k.ekle([b, b2])
    k.kaydet()
    okunan = Kayit(tmp_path).beyanlar()
    assert sorted(okunan, key=lambda x: x.accession_no) == sorted([b, b2], key=lambda x: x.accession_no)


def test_duplicates_ignored(tmp_path):
    k = Kayit(tmp_path)
    b = beyan()
    k.ekle([b])
    k.ekle([b])
    assert len(k.beyanlar()) == 1


def test_prune(tmp_path):
    k = Kayit(tmp_path)
    eski = beyan(gun=BUGUN - timedelta(days=40))
    yeni = beyan(gun=BUGUN - timedelta(days=2))
    k.ekle([eski, yeni])
    k.islendi(BUGUN - timedelta(days=40))
    k.islendi(BUGUN - timedelta(days=2))
    k.buda(BUGUN)
    assert k.beyanlar() == [yeni]
    assert k.islenen_gunler() == {BUGUN - timedelta(days=2)}


def test_sent_markers_persist(tmp_path):
    k = Kayit(tmp_path)
    g = date(2026, 10, 23)
    assert not k.gunluk_gonderildi_mi(g)
    k.gunluk_gonderildi(g)
    k.haftalik_gonderildi(date(2026, 10, 19))
    k.islendi(g)
    k.kaydet()
    k2 = Kayit(tmp_path)
    assert k2.gunluk_gonderildi_mi(g)
    assert k2.haftalik_gonderildi_mi(date(2026, 10, 19))
    assert not k2.haftalik_gonderildi_mi(date(2026, 10, 26))
    assert k2.islenen_gunler() == {g}


def test_missing_files_mean_empty(tmp_path):
    k = Kayit(tmp_path / "yok")
    assert k.beyanlar() == []
    assert k.islenen_gunler() == set()
