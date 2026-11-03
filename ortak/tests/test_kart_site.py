import json
from datetime import datetime, timezone
from pathlib import Path

from rasathane_ortak.kagit import Bolum, Hucre, Kart, Satir
from rasathane_ortak.kart_site import kartlari_yaz, slug
from rasathane_ortak.site import Kaynak

ZAMAN = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
KAYNAK = [Kaynak("Borsa İstanbul", "https://www.borsaistanbul.com/")]


def _kart() -> Kart:
    return Kart(
        fikir="Kart",
        ad="En Çok İşlem Görenler",
        tarih="03.11.2026",
        alt_baslik="3 öğe",
        satirlar=(
            Bolum("Birinci grup"),
            Satir(ust="AAA", alt="İş · 2027", sag=(Hucre("1.200 TL", kalin=True), Hucre("%3,2", vurgu=True))),
            Satir(ust="BBB", alt="Ak · 2027", sag=(Hucre("900 TL"),)),
        ),
        kaynak="Borsa İstanbul",
        sutunlar=("Varant", "Hacim", "Değişim"),
    )


def test_slug_turkce_harf() -> None:
    assert slug("En Çok İşlem Görenler") == "en-cok-islem-gorenler"
    assert slug("Dayanak Haritası") == "dayanak-haritasi"


def test_kart_sayfasi_bicim(tmp_path: Path) -> None:
    yollar = kartlari_yaz(tmp_path, "varant", "aksam", [_kart()], simdi=ZAMAN, kaynaklar=KAYNAK)
    assert yollar == [tmp_path / "varant" / "aksam-en-cok-islem-gorenler.json"]
    veri = json.loads(yollar[0].read_text(encoding="utf-8"))
    assert veri["baslik"] == "En Çok İşlem Görenler"
    assert veri["grafik"] == "yok"
    assert [s["anahtar"] for s in veri["sutunlar"]] == ["ust", "alt", "s0", "s1"]
    assert [s["baslik"] for s in veri["sutunlar"]] == ["Varant", "Ayrıntı", "Hacim", "Değişim"]
    assert veri["satirlar"][0] == {"ust": "Birinci grup", "alt": "", "s0": "", "s1": ""}
    assert veri["satirlar"][1] == {"ust": "AAA", "alt": "İş · 2027", "s0": "1.200 TL", "s1": "%3,2"}
    assert veri["satirlar"][2]["s1"] == ""


def test_bos_kart_atlanir(tmp_path: Path) -> None:
    bos = Kart(fikir="Kart", ad="Boş", tarih="", alt_baslik="", satirlar=(), kaynak="")
    assert kartlari_yaz(tmp_path, "varant", "sabah", [bos], simdi=ZAMAN, kaynaklar=KAYNAK) == []
