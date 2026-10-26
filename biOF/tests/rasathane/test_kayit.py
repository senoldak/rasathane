import json
from datetime import date

from bioseeder.rasathane.kayit import Kayit


def test_gidis_donus(tmp_path):
    k = Kayit()
    k.son_sabah_gunu = date(2026, 10, 23)
    k.haftalik.append(date(2026, 10, 26))
    k.gun_ici_artir(date(2026, 10, 23))
    k.edgar_imlec = "0001-26-1"
    k.isaretle(["a", "b"])
    k.yaz(tmp_path / "g.json")
    k2 = Kayit.oku(tmp_path / "g.json")
    assert k2 == k


def test_bos_dosya(tmp_path):
    k = Kayit.oku(tmp_path / "yok.json")
    assert k.son_sabah_gunu is None and not k.gonderildi_mi("a") and k.gun_ici_sayisi(date(2026, 1, 1)) == 0


def test_ikinci_kosu_gondermez(tmp_path):
    k = Kayit()
    k.isaretle(["NCT1:DURDURULDU:2026-10-23"])
    k.yaz(tmp_path / "g.json")
    assert Kayit.oku(tmp_path / "g.json").gonderildi_mi("NCT1:DURDURULDU:2026-10-23")


def test_olay_siniri(tmp_path):
    k = Kayit()
    k.isaretle([str(i) for i in range(6000)])
    k.yaz(tmp_path / "g.json")
    veri = json.loads((tmp_path / "g.json").read_text(encoding="utf-8"))
    assert len(veri["olaylar"]) == 5000 and veri["olaylar"][-1] == "5999"
