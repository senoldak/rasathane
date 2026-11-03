import json
import re
from datetime import date, datetime, timezone

from inseeder.kanal.site_aktar import SAYFA, aktar, puan, satirlar
from tests.kanal.yardimci import beyan

GUN = date(2026, 10, 23)
SIMDI = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
YASAK = re.compile(r"\b(al|sat|sinyal|öneri|fırsat)\b", re.IGNORECASE)


def test_ceo_buyuk_alim_tam_puan():
    # CEO +30, ≥ $1 Mn +35, pozisyon %50 artış +25, plan dışı +10; küme yok.
    assert puan(beyan(unvan="CEO", tutar=1_200_000.0), 1) == 100


def test_kume_puani_yalniz_birden_cok_kisi():
    b = beyan(unvan="Direktör", tutar=150_000.0)
    assert puan(b, 1) == 15 + 15 + 25 + 0 + 10
    assert puan(b, 2) == 15 + 15 + 25 + 30 + 10


def test_satis_puani_plan_disi_ve_tutar_ile_sinirli():
    assert puan(beyan(kod="S", unvan="CFO", tutar=6_000_000.0), 1) == 25


def test_satirlar_esik_ve_plan_filtresi():
    liste = [
        beyan(tutar=99_000.0),                       # alım eşiğinin altında
        beyan(tutar=200_000.0, plan=True),           # 10b5-1 planı
        beyan(sembol="KEEP", tutar=200_000.0),       # geçer
        beyan(kod="S", unvan="Direktör", tutar=9_000_000.0),  # satış yalnız CEO/CFO
        beyan(kod="S", unvan="CFO", tutar=5_500_000.0),       # geçer
    ]
    sonuc = satirlar(liste)
    assert sorted(s["hisse"] for s in sonuc) == ["KEEP", "KRNT"]
    assert {s["islem"] for s in sonuc} == {"Alım", "Satış"}


def test_kume_sayisi_yedi_gunle_sinirli():
    # Direktör (15): küme eklenince 100 tavanına takılmaz.
    eski = beyan(sembol="ABCD", unvan="Direktör", tutar=200_000.0, kisi="1", gun=date(2026, 10, 10))
    yakin = beyan(sembol="ABCD", unvan="Direktör", tutar=200_000.0, kisi="2", gun=date(2026, 10, 20))
    yeni = beyan(sembol="ABCD", unvan="Direktör", tutar=200_000.0, kisi="3", gun=GUN)
    puanlar = {s["tarih"]: s["puan"] for s in satirlar([eski, yakin, yeni])}
    # 23 Ekim'in 7 günlük penceresinde (17–23 Ekim) iki kişi var: küme +30.
    # 10 Ekim, pencere dışında kaldığı için tek kişi sayılır.
    assert puanlar["2026-10-23"] - puanlar["2026-10-20"] == 30
    assert puanlar["2026-10-10"] == puanlar["2026-10-20"]


def test_aktar_sema_ve_grafik_yok(tmp_path):
    yol = aktar(tmp_path, SIMDI, [beyan(tutar=200_000.0)])
    assert yol == tmp_path / "inseeder" / f"{SAYFA}.json"
    veri = json.loads(yol.read_text(encoding="utf-8"))
    assert veri["sema"] == 1 and veri["bolum"] == "inseeder" and veri["sayfa"] == SAYFA
    assert veri["grafik"] == "yok"
    assert not (tmp_path / "inseeder" / "seri").exists()
    assert [s["anahtar"] for s in veri["sutunlar"]] == [
        "tarih", "hisse", "sirket", "rol", "islem", "tutar", "puan",
    ]
    satir = veri["satirlar"][0]
    assert set(satir) <= {s["anahtar"] for s in veri["sutunlar"]} | {"seri"}
    assert satir["tarih"] == "2026-10-23" and satir["puan"] == puan(beyan(tutar=200_000.0), 1)


def test_metinde_yasakli_kelime_yok(tmp_path):
    veri = json.loads(aktar(tmp_path, SIMDI, [beyan()]).read_text(encoding="utf-8"))
    metin = [veri["baslik"], veri["aciklama"]] + [s["baslik"] for s in veri["sutunlar"]]
    for m in metin:
        assert not YASAK.search(m), m
