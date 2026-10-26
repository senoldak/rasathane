from datetime import date, timedelta

from inseeder.kanal.secim import gunluk_alimlar, haftalik_ozet, kanala_uygun
from tests.kanal.yardimci import beyan

GUN = date(2026, 10, 23)


def test_kanala_uygun():
    assert kanala_uygun(beyan(tutar=100_000))
    assert not kanala_uygun(beyan(tutar=99_999))
    assert not kanala_uygun(beyan(plan=True))
    assert kanala_uygun(beyan(kod="S", tutar=5_000_000, unvan="CFO"))
    assert not kanala_uygun(beyan(kod="S", tutar=5_000_000, unvan="Direktör"))
    assert not kanala_uygun(beyan(kod="S", tutar=4_999_999, unvan="CEO"))


def test_gunluk_top8_sorted_and_filtered():
    bs = [beyan(sembol=f"S{i}", tutar=100_000 + i * 10_000) for i in range(10)]
    bs += [beyan(sembol="KUCUK", tutar=99_999), beyan(sembol="PLAN", tutar=9e6, plan=True),
           beyan(sembol="SATIS", kod="S", tutar=9e6), beyan(sembol="DUN", tutar=9e6, gun=GUN - timedelta(days=1))]
    satirlar = gunluk_alimlar(bs, GUN)
    assert len(satirlar) == 8
    assert satirlar[0].beyan.sembol == "S9"
    assert [s.beyan.tutar for s in satirlar] == sorted([s.beyan.tutar for s in satirlar], reverse=True)
    assert not {"KUCUK", "PLAN", "SATIS", "DUN"} & {s.beyan.sembol for s in satirlar}


def test_cluster_two_people_within_7_days():
    bs = [beyan(sembol="KRNT", kisi="A", gun=GUN - timedelta(days=5)), beyan(sembol="KRNT", kisi="B")]
    assert gunluk_alimlar(bs, GUN)[0].kume is True


def test_cluster_same_person_not_counted():
    bs = [beyan(sembol="KRNT", kisi="A", gun=GUN - timedelta(days=5)), beyan(sembol="KRNT", kisi="A")]
    assert gunluk_alimlar(bs, GUN)[0].kume is False


def test_cluster_window_excludes_day_8():
    bs = [beyan(sembol="KRNT", kisi="A", gun=GUN - timedelta(days=7)), beyan(sembol="KRNT", kisi="B")]
    assert gunluk_alimlar(bs, GUN)[0].kume is False


def test_cluster_ignores_small_purchases():
    bs = [beyan(sembol="KRNT", kisi="A", tutar=50_000), beyan(sembol="KRNT", kisi="B")]
    assert gunluk_alimlar(bs, GUN)[0].kume is False


def test_degisim_filled():
    s = gunluk_alimlar([beyan()], GUN)[0]
    assert s.degisim == 0.5


def test_haftalik_ozet():
    pzt = date(2026, 10, 19)
    bs = [
        beyan(sembol="AAA", kisi="1", gun=pzt), beyan(sembol="AAA", kisi="2", gun=pzt + timedelta(days=2)),
        beyan(sembol="AAA", kisi="3", gun=GUN),
        beyan(sembol="BBB", kisi="4", gun=pzt, tutar=9e6), beyan(sembol="BBB", kisi="5", gun=GUN, tutar=9e6),
        beyan(sembol="CCC", kisi="6", gun=GUN),
        beyan(sembol="OLD", kisi="7", gun=pzt - timedelta(days=3)), beyan(sembol="OLD", kisi="8", gun=pzt),
        beyan(sembol="S1", kod="S", unvan="CEO", tutar=6e6),
        beyan(sembol="S2", kod="S", unvan="Direktör", tutar=9e6),
        beyan(sembol="S3", kod="S", unvan="CFO", tutar=4e6),
        beyan(sembol="S4", kod="S", unvan="CEO", tutar=8e6, plan=True),
    ]
    ozet = haftalik_ozet(bs, GUN)
    assert ozet.gunler[0] == pzt
    assert [k.sembol for k in ozet.kumeler] == ["AAA", "BBB"]
    assert ozet.kumeler[0].kisi_sayisi == 3
    assert ozet.kumeler[1].toplam == 18e6
    assert [s.sembol for s in ozet.satislar] == ["S1"]


def test_split_joint_filing_counted_once():
    # Form 4 en çok 10 raporlayan alır; aynı alım ikinci beyanla tekrarlanabilir (RENT, 23.10.2026).
    a = beyan(sembol="RENT", kisi="1", tutar=2_250_000)
    b = beyan(sembol="RENT", kisi="2", tutar=2_250_000)
    satirlar = gunluk_alimlar([a, b], GUN)
    assert len(satirlar) == 1
    assert satirlar[0].kume is False
    assert haftalik_ozet([a, b], GUN).kumeler == []


def test_split_sale_filing_counted_once():
    a = beyan(sembol="TRV", kod="S", unvan="CEO", tutar=9e6)
    b = beyan(sembol="TRV", kod="S", unvan="CEO", tutar=9e6)
    assert len(haftalik_ozet([a, b], GUN).satislar) == 1
