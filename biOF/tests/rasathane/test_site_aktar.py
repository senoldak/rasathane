import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from bioseeder.rasathane import isler
from bioseeder.rasathane.__main__ import argumanlar
from bioseeder.rasathane.ctgov import Calisma, goruntu_yaz
from bioseeder.rasathane.edgar import Bildirim
from bioseeder.rasathane.evren import Sirket
from bioseeder.rasathane.isler import Baglam, sabah_isi
from bioseeder.rasathane.olay import Olay, OlayTuru
from bioseeder.rasathane.site_aktar import olaylar_aktar, takvim_aktar

CMT = date(2026, 10, 24)
FAZ3 = "AAA Announces Topline Results from Phase 3 STAR Trial (NCT00000001)"
YASAK = re.compile(r"\b(al|sat|sinyal|öneri|fırsat)\b", re.IGNORECASE)


def _c(nct, ticker="AAA", bitis="2026-11-20", hassas="GUN", durum="RECRUITING", faz="3"):
    return Calisma(nct=nct, ticker=ticker, faz=faz, durum=durum, bitis=bitis, bitis_hassas=hassas,
                   sonuc=False, ilac="Ilac", hastalik="Hastalik")


def _olay(ticker="AAA", tarih=CMT, tur=OlayTuru.FAZ3_SONUC, satir="Ilac · Hastalik", mikro=False):
    return Olay(kimlik=f"{ticker}:{tarih}:{tur.name}", tur=tur, ticker=ticker, satir=satir,
                ayrinti="SEC 8-K · 24.10.2026", tarih=tarih, faz3=True, mikro=mikro)


def _fiyat(cagrilar=None, hatali=()):
    def cek(ticker, bas, son):
        if cagrilar is not None:
            cagrilar.append(ticker)
        if ticker in hatali:
            raise RuntimeError("Yahoo engelledi")
        n = (son - bas).days + 1
        return [(bas + timedelta(days=i), 10.0 + i * 0.1) for i in range(n)]

    return cek


def _oku(yol: Path):
    return json.loads(yol.read_text(encoding="utf-8"))


def test_takvim_pencere_ve_alanlar(tmp_path):
    goruntu = {
        "N1": _c("N1", bitis="2026-11-20"),
        "N2": _c("N2", ticker="BBB", bitis="2026-12", hassas="AY", faz="2/3"),
        "N3": _c("N3", bitis="2027-06-01"),  # 60 günün dışında
        "N4": _c("N4", ticker="CCC", bitis="2026-11-10", durum="COMPLETED"),  # kapalı çalışma
    }
    yol = takvim_aktar(tmp_path, CMT, goruntu, {"AAA": True, "BBB": False})
    veri = _oku(yol)
    assert veri["bolum"] == "biof" and veri["sayfa"] == "takvim" and veri["sema"] == 1
    satirlar = {r["ticker"]: r for r in veri["satirlar"]}
    assert set(satirlar) == {"AAA", "BBB"}
    assert satirlar["AAA"]["bitis"] == "20.11.2026"
    assert satirlar["AAA"]["kalan_gun"] == 27
    assert satirlar["AAA"]["mikro"] == "MİKRO"
    assert satirlar["BBB"]["bitis"] == "12.2026"
    assert satirlar["BBB"]["kalan_gun"] is None  # yalnız ay bilinen tarihte gün sayılmaz
    assert satirlar["BBB"]["faz"] == "2/3"
    assert "seri" not in satirlar["AAA"]  # fiyat kaynağı yoksa grafik yok


def test_olaylar_yinelenmez_ve_eski_satir_duser(tmp_path):
    eski = {"sema": 1, "bolum": "biof", "sayfa": "olaylar", "baslik": "x", "aciklama": "x",
            "guncellendi": "2025-01-01T00:00:00Z", "kaynaklar": [], "sutunlar": [], "suzgecler": [],
            "grafik": "cizgi", "satirlar": [{"tarih": "2025-01-01", "ticker": "ZZZ", "etiket": "FDA ONAY",
                                              "satir": "Eski", "ayrinti": "", "mikro": ""}]}
    (tmp_path / "biof").mkdir()
    (tmp_path / "biof" / "olaylar.json").write_text(json.dumps(eski), encoding="utf-8")

    olaylaar = [_olay(), _olay(ticker="BBB", tur=OlayTuru.FDA_RET, satir="Ilac2 · Hastalik2")]
    olaylar_aktar(tmp_path, CMT, olaylaar)
    olaylar_aktar(tmp_path, CMT, olaylaar)  # aynı koşu iki kez: satır çoğalmaz
    satirlar = _oku(tmp_path / "biof" / "olaylar.json")["satirlar"]
    assert len(satirlar) == 2
    assert {r["ticker"] for r in satirlar} == {"AAA", "BBB"}
    assert all(r["tarih"] >= "2025-10-24" for r in satirlar)  # 365 günden eski satır düşer


def test_seri_gostergeli_ve_olay_isareti(tmp_path):
    olaylar_aktar(tmp_path, CMT, [_olay()], fiyat=_fiyat())
    seri = _oku(tmp_path / "biof" / "seri" / "AAA.json")
    assert len(seri["tarihler"]) == 252  # son 1 yıl, işlem günü sayısı
    assert {"kapanis", "ema144", "ema233", "ema377", "rsi14"} <= set(seri["sutunlar"])
    assert len(seri["sutunlar"]["kapanis"]) == 252
    assert seri["tarihler"][-1] == "2026-10-25"  # bugün+1 en son sütun
    assert ["2026-10-24", "FAZ 3 SONUÇ"] in seri["isaretler"]
    haftalik = _oku(tmp_path / "biof" / "seri" / "AAA-hafta.json")
    assert set(haftalik["sutunlar"]) == {"kapanis", "ema144", "ema233", "rsi14"}
    assert len(haftalik["tarihler"]) <= 104

    veri = _oku(olaylar_aktar(tmp_path, CMT, [_olay()], fiyat=_fiyat()))
    assert veri["satirlar"][0]["seri"] == "AAA"


def test_bir_hissenin_fiyatı_yoksa_sayfa_yine_yazılır(tmp_path):
    cagrilar = []
    yol = olaylar_aktar(tmp_path, CMT, [_olay(), _olay(ticker="BBB", tur=OlayTuru.FDA_RET)],
                        fiyat=_fiyat(cagrilar, hatali=("BBB",)))
    assert sorted(cagrilar) == ["AAA", "BBB"]
    assert (tmp_path / "biof" / "seri" / "AAA.json").exists()
    assert not (tmp_path / "biof" / "seri" / "BBB.json").exists()
    satirlar = {r["ticker"]: r for r in _oku(yol)["satirlar"]}
    assert satirlar["AAA"]["seri"] == "AAA"
    assert "seri" not in satirlar["BBB"]


def test_sayfa_metinleri_yasak_sozcuk_icermez(tmp_path):
    for yol in (takvim_aktar(tmp_path, CMT, {}, {}), olaylar_aktar(tmp_path, CMT, [_olay()])):
        veri = _oku(yol)
        metin = " ".join([veri["baslik"], veri["aciklama"]] + [s["baslik"] for s in veri["sutunlar"]])
        assert not YASAK.search(metin), metin


def test_cli_site_argumani():
    assert argumanlar(["sabah", "--site", "../site-veri"]).site == Path("../site-veri")
    assert argumanlar(["sabah"]).site is None


class _Kaynak:
    def __init__(self, bulten=FAZ3):
        self.bulten_metni = bulten

    def evren(self):
        return [Sirket("AAA", 1, "Aaa Bio Inc", "Nasdaq", 2834, 500.0)], {}

    def ctgov_guncel(self, gun, sponsorlar, eslesmeyen):
        return []

    def edgar_gunluk(self, gun):
        return [Bildirim("0001-26-000001", 1, "Aaa Bio Inc", gun)]

    def bulten(self, b):
        return self.bulten_metni


class _Telegram:
    def sirayla(self, *a, **k):
        raise AssertionError("kuru koşuda gönderim olmamalı")

    def sahibe(self, metin):
        pass


def _baglam(tmp_path, site):
    veri = tmp_path / "veri"
    veri.mkdir()
    goruntu_yaz({"NCT00000001": _c("NCT00000001")}, veri / "ctgov.csv")
    return Baglam(kaynak=_Kaynak(), telegram=_Telegram(), kuru=True, bugun=CMT, veri=veri,
                  cikti=tmp_path / "cikti", site=site)


def test_sabah_kuru_koşu_site_verisi_yazar(tmp_path):
    site = tmp_path / "site"
    b = _baglam(tmp_path, site)
    assert sabah_isi(b, CMT - timedelta(days=1)) == 1
    satirlar = _oku(site / "biof" / "olaylar.json")["satirlar"]
    assert [(r["etiket"], r["ticker"]) for r in satirlar] == [("FAZ 3 SONUÇ", "AAA")]


def test_site_kapaliyken_dosya_yazilmaz(tmp_path):
    b = _baglam(tmp_path, None)
    sabah_isi(b, CMT - timedelta(days=1))
    assert not (tmp_path / "site").exists()


def test_site_hatasi_sabahı_durdurmaz(tmp_path, monkeypatch, capsys):
    def patla(*a, **k):
        raise OSError("disk dolu")

    monkeypatch.setattr(isler, "olaylar_aktar", patla)
    b = _baglam(tmp_path, tmp_path / "site")
    assert sabah_isi(b, CMT - timedelta(days=1)) == 1
    assert "biOF site verisi yazılamadı (sabah): OSError: disk dolu" in capsys.readouterr().err
