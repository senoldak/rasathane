import datetime
import json
import re

from capitolseeder.kanal.arsiv import beyanlari_yaz
from capitolseeder.kanal.site_aktar import main, site_aktar
from tests.kanal.yardimci import beyan

SIMDI = datetime.datetime(2026, 11, 2, 12, 0, tzinfo=datetime.timezone.utc)
YASAKLI = re.compile(r"\b(al|sat|sinyal|öneri|fırsat)\b", re.IGNORECASE)


def _oku(yol):
    return json.loads(yol.read_text(encoding="utf-8"))


def test_sayfa_sema_ve_sutunlar(tmp_path):
    yol = site_aktar(tmp_path, SIMDI, [beyan(id="x")])
    assert yol == tmp_path / "capital" / "beyanlar.json"
    veri = _oku(yol)
    assert veri["sema"] == 1
    assert veri["bolum"] == "capital" and veri["sayfa"] == "beyanlar"
    assert veri["guncellendi"] == "2026-11-02T12:00:00Z"
    assert veri["grafik"] == "yok"
    assert [s["anahtar"] for s in veri["sutunlar"]] == [
        "bildirim", "uye", "parti", "meclis", "varlik", "islem", "tutar", "uyum", "gecikme", "belge",
    ]
    assert all("seri" not in r for r in veri["satirlar"])  # hisse fiyat geçmişi yok: grafik de yok


def test_satir_alanlari_ve_eslemeler(tmp_path):
    yol = site_aktar(
        tmp_path,
        SIMDI,
        [
            beyan(id="a", islem="Purchase", ticker="NVDA", parti="D", gec=False, gecikme=21),
            beyan(id="b", islem="Sale (Partial)", ticker="", varlik="US Treasury Note 3.375%", gec=True, parti="R"),
            beyan(id="c", islem="Exchange", ticker="", varlik="Bir Şirket Ltd.", parti="I"),
        ],
    )
    satirlar = {r["varlik"]: r for r in _oku(yol)["satirlar"]}
    nvda = satirlar["NVDA"]
    assert nvda["islem"] == "Alış" and nvda["parti"] == "Demokrat" and nvda["uyum"] == "Zamanında"
    assert nvda["gecikme"] == 21 and nvda["bildirim"] == "2026-10-22"
    tahvil = satirlar["US Treasury Note 3.375%"]
    assert tahvil["islem"] == "Satış" and tahvil["uyum"] == "Geç" and tahvil["parti"] == "Cumhuriyetçi"
    assert satirlar["Bir Şirket Ltd."]["islem"] == "Değişim"


def test_sirali_en_yeni_ustte_ve_belge(tmp_path):
    yol = site_aktar(
        tmp_path,
        SIMDI,
        [
            beyan(id="eski", beyan_tarihi=datetime.date(2026, 9, 1)),
            beyan(id="yeni", beyan_tarihi=datetime.date(2026, 10, 30), belge="https://example.org/yeni.pdf"),
        ],
    )
    satirlar = _oku(yol)["satirlar"]
    assert [r["bildirim"] for r in satirlar] == ["2026-10-30", "2026-09-01"]
    assert satirlar[0]["belge"] == "https://example.org/yeni.pdf"


def test_kaynaklar_ve_yasakli_sozcuk_yok(tmp_path):
    yol = site_aktar(tmp_path, SIMDI, [beyan(id="x", islem="Purchase"), beyan(id="y", islem="Sale (Full)")])
    veri = _oku(yol)
    assert {k["url"] for k in veri["kaynaklar"]} >= {"https://disclosures-clerk.house.gov/"}
    metin = " ".join(
        [veri["baslik"], veri["aciklama"]]
        + [str(v) for r in veri["satirlar"] for k, v in r.items() if k != "belge"]
    )
    assert YASAKLI.search(metin) is None


def test_veri_yoksa_dosya_yazilmaz(tmp_path):
    assert site_aktar(tmp_path, SIMDI, []) is None
    assert not (tmp_path / "capital").exists()


def test_komut_satiri_csvden_yazar(tmp_path):
    veri = tmp_path / "veri"
    beyanlari_yaz(veri / "beyanlar.csv", [beyan(id="x")])
    kok = tmp_path / "site-veri"
    assert main(["--veri", str(veri), "--kok", str(kok)]) == 0
    assert _oku(kok / "capital" / "beyanlar.json")["satirlar"][0]["uye"] == "Richard W. Allen"
