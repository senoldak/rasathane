from datetime import date, timedelta

import pytest

from bioseeder.rasathane.ctgov import Calisma, goruntu_yaz
from bioseeder.rasathane.edgar import Bildirim
from bioseeder.rasathane.evren import Sirket
from bioseeder.rasathane.isler import Baglam, calistir, gun_ici_isi, haftalik_isi, sabah_isi
from bioseeder.rasathane.kayit import Kayit
from bioseeder.rasathane.http import KaynakHatasi
from bioseeder.rasathane.telegram import TelegramHatasi

SIRKETLER = [Sirket("AAA", 1, "Aaa Bio Inc", "Nasdaq", 2834, 500.0),
             Sirket("BBB", 2, "Bbb Therapeutics", "Nasdaq", 2836, 20.0)]
FAZ3 = "AAA Announces Topline Results from Phase 3 STAR Trial (NCT00000001)"
RET = "BBB Receives Complete Response Letter from FDA"
FAZ2 = "AAA Reports Topline Data from Phase 2 Study"


def _c(nct, **kw):
    t = dict(nct=nct, ticker="AAA", faz="3", durum="RECRUITING", bitis="2027-06-01", bitis_hassas="GUN",
             sonuc=False, ilac="Ilac", hastalik="Hastalik")
    t.update(kw)
    return Calisma(**t)


class SahteKaynak:
    def __init__(self, ctgov=None, gunluk=None, bultenler=None, guncel=None, pist=None):
        self.ctgov = ctgov or {}
        self.gunluk = gunluk or {}
        self.bultenler = bultenler or {}
        self.guncel = guncel or []
        self.pist = pist or {}
        self.istenen_gunler = []
        self.kapali = set()

    def evren(self):
        return SIRKETLER, {}

    def ctgov_guncel(self, gun, sponsorlar, eslesmeyen):
        self.istenen_gunler.append(gun)
        return self.ctgov.get(gun, [])

    def edgar_gunluk(self, gun):
        if gun in self.kapali:
            raise KaynakHatasi("EDGAR günlük dizini yok", 404)
        return self.gunluk.get(gun, [])

    def edgar_guncel(self, imlec):
        return self.guncel, (self.guncel[0].erisim if self.guncel else imlec)

    def bulten(self, b):
        if b.erisim not in self.bultenler:
            raise KaynakHatasi("Bulunamadı", 404)
        return self.bultenler[b.erisim]

    def nakit_pisti(self, ticker):
        return self.pist.get(ticker)


class SahteTelegram:
    def __init__(self, hata=False, hatali_deneme=None):
        self.gonderilen = []  # (kart, sayfa, aciklama)
        self.sahibe_giden = []
        self.hata = hata
        self.hatali_deneme = hatali_deneme  # kaçıncı gönderim denemesi (1'den) bir kez düşsün
        self.deneme = 0

    def sirayla(self, gun, gidenler, kayit, sonrasi=None):
        ids = []
        for g in gidenler:
            if kayit.gonderildi_mi(gun, g.kart, g.sayfa):
                continue
            self.deneme += 1
            if self.hata or self.deneme == self.hatali_deneme:
                raise TelegramHatasi("Bad Request")
            self.gonderilen.append((g.kart, g.sayfa, g.aciklama))
            kayit.ekle(gun, g.kart, g.sayfa, 1)
            if sonrasi:
                sonrasi(g, 1)
            ids.append(1)
        return ids

    def sahibe(self, metin):
        self.sahibe_giden.append(metin)


G = date(2026, 10, 23)  # Cuma
CMT = date(2026, 10, 24)


def _baglam(tmp_path, kaynak, tg=None, kuru=False, bugun=CMT, gonderim_acik=False):
    veri = tmp_path / "veri"
    veri.mkdir(exist_ok=True)
    if not (veri / "ctgov.csv").exists():
        goruntu_yaz({"NCT00000001": _c("NCT00000001"), "NCT2": _c("NCT2")}, veri / "ctgov.csv")
    return Baglam(kaynak=kaynak, telegram=tg or SahteTelegram(), kuru=kuru, bugun=bugun, veri=veri,
                  cikti=tmp_path / "cikti", gonderim_acik=gonderim_acik)


def _b(erisim, cik=1, tarih=G):
    return Bildirim(erisim, cik, "X", tarih)


def test_sabah_olaysiz_gondermez(tmp_path):
    b = _baglam(tmp_path, SahteKaynak())
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert b.telegram.gonderilen == []
    assert Kayit.oku(b.veri / "gonderilen.json").son_sabah_gunu == G


def _sekiz_olay():
    yeni = [_c(f"NCT9{i}", ilk_kayit=G.isoformat()) for i in range(7)]
    return SahteKaynak(ctgov={G: yeni}, gunluk={G: [_b("ret-1", cik=2)]}, bultenler={"ret-1": RET})


def test_sabah_iki_sayfa_ayri_mesaj(tmp_path):
    b = _baglam(tmp_path, _sekiz_olay())
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert [a for _, _, a in b.telegram.gonderilen] == [
        "biOF · Sabah Bülteni (1/2) · 23.10.2026", "biOF · Sabah Bülteni (2/2) · 23.10.2026"]
    assert len(Kayit.oku(b.veri / "gonderilen.json").olaylar) == 8
    assert (b.veri / "gonderilen_kartlar.csv").exists()


def _on_uc_olay():
    yeni = [_c(f"NCT7{i:02d}", ilk_kayit=G.isoformat()) for i in range(12)]
    return SahteKaynak(ctgov={G: yeni}, gunluk={G: [_b("ret-1", cik=2)]}, bultenler={"ret-1": RET})


def test_sabah_sayfa_dusunce_kalan_olaylar(tmp_path):
    k = _on_uc_olay()
    b = _baglam(tmp_path, k, tg=SahteTelegram(hatali_deneme=2))
    assert calistir("sabah", lambda: sabah_isi(b), b) == 1
    assert len(b.telegram.gonderilen) == 1
    kayit = Kayit.oku(b.veri / "gonderilen.json")
    assert len(kayit.olaylar) == 6 and kayit.son_sabah_gunu is None
    ikinci = SahteTelegram()
    b2 = _baglam(tmp_path, k, tg=ikinci)
    assert calistir("sabah", lambda: sabah_isi(b2), b2) == 0
    assert [a for _, _, a in ikinci.gonderilen] == [
        "biOF · Sabah Bülteni (1/2) · 23.10.2026", "biOF · Sabah Bülteni (2/2) · 23.10.2026"]
    kayit = Kayit.oku(b.veri / "gonderilen.json")
    assert len(kayit.olaylar) == 13 and kayit.son_sabah_gunu == G


def test_ikinci_kosu_gondermez(tmp_path):
    k = _sekiz_olay()
    b = _baglam(tmp_path, k)
    sabah_isi(b)
    ilk = len(b.telegram.gonderilen)
    sabah_isi(_baglam(tmp_path, k, tg=b.telegram))
    assert ilk == 2 and len(b.telegram.gonderilen) == ilk


def test_gonderim_hatasi_kaydi_yazmaz(tmp_path):
    b = _baglam(tmp_path, _sekiz_olay(), tg=SahteTelegram(hata=True))
    assert calistir("sabah", lambda: sabah_isi(b), b) == 1
    assert not (b.veri / "gonderilen.json").exists()
    assert "sabah" in b.telegram.sahibe_giden[0]
    assert "NCT90" not in (b.veri / "ctgov.csv").read_text(encoding="utf-8")


def test_kuru_gondermez_dosya_yazar(tmp_path):
    b = _baglam(tmp_path, _sekiz_olay(), kuru=True)
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert b.telegram.gonderilen == []
    assert len(list((tmp_path / "cikti").glob("sabah-*.png"))) == 2
    assert len(list((tmp_path / "cikti").glob("sabah-*.txt"))) == 1
    assert not (b.veri / "gonderilen.json").exists()
    assert "NCT90" in (b.veri / "ctgov.csv").read_text(encoding="utf-8")


def test_150_esigi(tmp_path):
    k = SahteKaynak(ctgov={G: [_c(f"NCT8{i:03d}", ilk_kayit=G.isoformat()) for i in range(151)]})
    b = _baglam(tmp_path, k)
    assert calistir("sabah", lambda: sabah_isi(b), b) == 1
    assert b.telegram.gonderilen == []


def test_kacan_gun_telafi(tmp_path):
    k = SahteKaynak()
    b = _baglam(tmp_path, k)
    kayit = Kayit()
    kayit.son_sabah_gunu = date(2026, 10, 20)
    kayit.yaz(b.veri / "gonderilen.json")
    sabah_isi(b)
    assert k.istenen_gunler == [date(2026, 10, 21), date(2026, 10, 22), G]


def test_nct_baglama(tmp_path, monkeypatch):
    import bioseeder.rasathane.isler as isler

    gorulen = []
    asil = isler.kart

    def yakala(ad, tarih, kutucuklar, *a, **kw):
        gorulen.extend(kutucuklar)
        return asil(ad, tarih, kutucuklar, *a, **kw)

    monkeypatch.setattr(isler, "kart", yakala)
    k = SahteKaynak(gunluk={G: [_b("f3-1"), _b("f2-1")]}, bultenler={"f3-1": FAZ3, "f2-1": FAZ2})
    b = _baglam(tmp_path, k, kuru=True)
    sabah_isi(b)
    assert {"FAZ 3 SONUÇ", "FAZ 2 SONUÇ"} <= {k.etiket for k in gorulen}
    aciklama = next((tmp_path / "cikti").glob("sabah-*.txt")).read_text(encoding="utf-8")
    assert aciklama.strip() == "biOF · Sabah Bülteni · 23.10.2026"
    from bioseeder.rasathane.isler import _bildirim_olayi
    assert _bildirim_olayi(_b("x"), FAZ3, SIRKETLER[0], {"NCT00000001": _c("NCT00000001")}).satir == "Ilac · Hastalik"
    assert _bildirim_olayi(_b("x"), FAZ2, SIRKETLER[0], {}).satir == "Ayrıntı: 8-K basın bülteni"


def test_gun_ici_gunde_iki(tmp_path):
    guncel = [_b("g1"), _b("g2", cik=2), _b("g3"), _b("g4")]
    k = SahteKaynak(guncel=guncel, bultenler={"g1": FAZ3, "g2": RET, "g3": FAZ3, "g4": FAZ2})
    b = _baglam(tmp_path, k, bugun=G)
    gun_ici_isi(b)
    assert len(b.telegram.gonderilen) == 2
    assert all(a.startswith("biOF · Büyük Olay · ") for _, _, a in b.telegram.gonderilen)
    kayit = Kayit.oku(b.veri / "gonderilen.json")
    assert kayit.gun_ici_sayisi(G) == 2 and kayit.edgar_imlec == "g1"
    gun_ici_isi(_baglam(tmp_path, k, tg=b.telegram, bugun=G))
    assert len(b.telegram.gonderilen) == 2


def test_haftalik(tmp_path):
    pzt = date(2026, 10, 26)
    k = SahteKaynak(pist={"AAA": 4.5})
    b = _baglam(tmp_path, k, bugun=pzt)
    goruntu_yaz({"N1": _c("N1", bitis="2026-11-20")}, b.veri / "ctgov.csv")
    assert haftalik_isi(b) == 1
    assert haftalik_isi(_baglam(tmp_path, k, tg=b.telegram, bugun=pzt)) == 0
    assert len(b.telegram.gonderilen) == 1


def test_haftalik_pist_okunamazsa_hata(tmp_path):
    b = _baglam(tmp_path, SahteKaynak(), bugun=date(2026, 10, 26))
    goruntu_yaz({"N1": _c("N1", bitis="2026-11-20")}, b.veri / "ctgov.csv")
    assert calistir("haftalik", lambda: haftalik_isi(b), b) == 1


def test_federal_tatilde_edgar_atlanir(tmp_path):
    veterans = date(2026, 11, 11)
    k = SahteKaynak()
    k.kapali = {veterans}
    b = _baglam(tmp_path, k, bugun=date(2026, 11, 12))
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert k.istenen_gunler == [veterans]  # ClinicalTrials.gov yine sorgulanır
    assert Kayit.oku(b.veri / "gonderilen.json").son_sabah_gunu == veterans


def test_is_gununde_edgar_dizini_yoksa_hata(tmp_path):
    k = SahteKaynak()
    k.kapali = {G}
    b = _baglam(tmp_path, k)
    assert calistir("sabah", lambda: sabah_isi(b), b) == 1


def test_gonderim_acikken_kuru_goruntu_yazmaz(tmp_path):
    b = _baglam(tmp_path, _sekiz_olay(), kuru=True, gonderim_acik=True)
    sabah_isi(b)
    assert "NCT90" not in (b.veri / "ctgov.csv").read_text(encoding="utf-8")
    assert len(list((tmp_path / "cikti").glob("sabah-*.png"))) == 2


def test_bulten_okunamazsa_atlanir(tmp_path):
    k = SahteKaynak(gunluk={G: [_b("yok-1"), _b("f3-1")]}, bultenler={"f3-1": FAZ3})
    b = _baglam(tmp_path, k)
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert len(b.telegram.gonderilen) == 1


def _fiyat_cekici(cagrilar, bitis=G):
    def cek(ticker, bas, son):
        cagrilar.append(ticker)
        n = (bitis - bas).days + 1
        return [(bas + timedelta(days=i), 10.0 + i * 0.1) for i in range(n)]
    return cek


def test_grafik_sayfalardan_sonra_en_onemli_olay(tmp_path):
    cagrilar = []
    b = _baglam(tmp_path, _on_uc_olay())
    b.fiyat_cekici = _fiyat_cekici(cagrilar)
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert [a for _, _, a in b.telegram.gonderilen] == [
        "biOF · Sabah Bülteni (1/3) · 23.10.2026", "biOF · Sabah Bülteni (2/3) · 23.10.2026",
        "biOF · Sabah Bülteni (3/3) · 23.10.2026", "biOF · Olay Grafiği · 23.10.2026"]
    assert cagrilar == ["BBB"]  # FDA ret mektubu bültenin en önemli olayı


def test_olay_gunu_fiyatta_yoksa_atla(tmp_path):
    b = _baglam(tmp_path, _sekiz_olay())
    b.fiyat_cekici = _fiyat_cekici([], bitis=G - timedelta(days=1))
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert [a for _, _, a in b.telegram.gonderilen] == [
        "biOF · Sabah Bülteni (1/2) · 23.10.2026", "biOF · Sabah Bülteni (2/2) · 23.10.2026"]
    assert any("Olay Grafiği" in m for m in b.telegram.sahibe_giden)
    assert Kayit.oku(b.veri / "gonderilen.json").son_sabah_gunu == G


class GrafikteDusenTelegram(SahteTelegram):
    def sirayla(self, gun, gidenler, kayit, sonrasi=None):
        if any(g.kart.startswith("grafik:") for g in gidenler):
            raise TelegramHatasi("Bad Gateway")
        return super().sirayla(gun, gidenler, kayit, sonrasi)


def test_grafik_gonderilemezse_bulten_durumu_yazilir(tmp_path):
    tg = GrafikteDusenTelegram()
    b = _baglam(tmp_path, _sekiz_olay(), tg=tg)
    b.fiyat_cekici = _fiyat_cekici([])
    assert calistir("sabah", lambda: sabah_isi(b), b) == 0
    assert len(tg.gonderilen) == 2
    assert any("Olay Grafiği" in m for m in tg.sahibe_giden)
    assert Kayit.oku(b.veri / "gonderilen.json").son_sabah_gunu == G
    assert "NCT90" in (b.veri / "ctgov.csv").read_text(encoding="utf-8")
