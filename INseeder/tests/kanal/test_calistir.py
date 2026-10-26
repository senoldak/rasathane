import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from inseeder.kanal import calistir as calistir_mod
from inseeder.kanal.calistir import Ayarlar, calistir, main
from inseeder.kanal.sec import GunSonucu, KanalHatasi
from inseeder.kanal.telegram import TelegramIstemcisi
from tests.kanal.yardimci import beyan


class SahteSec:
    def __init__(self, gunler=None, hata=None):
        self.gunler = gunler or {}
        self.hata = hata
        self.cagrilar = []

    def gun_isle(self, gun, bekle_404=True):
        self.cagrilar.append((gun, bekle_404))
        if self.hata:
            raise self.hata
        if gun in self.gunler:
            return self.gunler[gun]
        return GunSonucu(gun=gun, dizin_var=True, toplam=150, okunan=150)


class SahteTelegram:
    def __init__(self, durum=200, hatali_foto=None):
        self.istekler = []
        self.durum = durum
        self.hatali_foto = hatali_foto  # kaçıncı sendPhoto (1'den) kalıcı hata versin
        self.foto = 0

    def __call__(self, req):
        self.istekler.append(req)
        if "sendPhoto" in req.url.path:
            self.foto += 1
            if self.foto == self.hatali_foto:
                return httpx.Response(400, json={"ok": False, "description": "Bad Request: TOPIC_CLOSED"})
        if self.durum != 200 and "sendMessage" not in req.url.path:
            return httpx.Response(self.durum, json={"ok": False, "description": "boom"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.istekler)}})

    def yollar(self):
        return [r.url.path.rsplit("/", 1)[1] for r in self.istekler]

    def aciklamalar(self):
        return [r.content.decode("utf-8", errors="replace") for r in self.istekler if "sendPhoto" in r.url.path]

    def istemci(self):
        return TelegramIstemcisi(httpx.Client(transport=httpx.MockTransport(self)), "T", uyku=lambda s: None)


def _gun(g, *beyanlar, dizin_var=True):
    return GunSonucu(gun=g, dizin_var=dizin_var, toplam=150 if dizin_var else 0,
                     okunan=150 if dizin_var else 0, beyanlar=list(beyanlar))


def _ayar(tmp_path, bugun, **kw):
    d = dict(kuru=False, tarih=None, doldur=7, cikti=tmp_path / "cikti", veri=tmp_path / "veri",
             bugun=bugun, hedef="@rasathane:42", token="T", sahip_id="99")
    d.update(kw)
    return Ayarlar(**d)


SALI = date(2026, 10, 27)
PZT = date(2026, 10, 26)


def test_dry_run_writes_cards_not_records(tmp_path):
    tg = SahteTelegram()
    sonuc = calistir(_ayar(tmp_path, SALI, kuru=True), SahteSec({PZT: _gun(PZT, beyan(gun=PZT))}), tg.istemci())
    assert sonuc == "kuru"
    assert (tmp_path / "cikti" / "gunluk_2026-10-26.png").exists()
    assert (tmp_path / "cikti" / "aciklama_2026-10-26.txt").exists()
    assert not (tmp_path / "veri").exists()
    assert tg.istekler == []


def test_no_target_updates_records_without_sending(tmp_path):
    tg = SahteTelegram()
    sonuc = calistir(_ayar(tmp_path, SALI, hedef=None), SahteSec({PZT: _gun(PZT, beyan(gun=PZT))}), tg.istemci())
    assert sonuc == "kuru"
    assert (tmp_path / "veri" / "beyanlar.csv").exists()
    durum = json.loads((tmp_path / "veri" / "gonderilenler.json").read_text(encoding="utf-8"))
    assert durum["gunluk"] == []
    assert "2026-10-26" in durum["islenen"]
    assert tg.istekler == []


def test_sends_once_per_day(tmp_path):
    tg = SahteTelegram()
    b = beyan(gun=PZT)
    sec = SahteSec({PZT: _gun(PZT, b)})
    assert calistir(_ayar(tmp_path, SALI), sec, tg.istemci()) == "gonderildi"
    assert calistir(_ayar(tmp_path, SALI), sec, tg.istemci()) == "zaten_gonderildi"
    assert tg.yollar() == ["sendPhoto"]
    satirlar = (tmp_path / "veri" / "beyanlar.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(satirlar) == 2


CUMA = date(2026, 10, 30)


def _cuma_sec():
    return SahteSec({CUMA: _gun(CUMA, beyan(sembol="KRNT", kisi="B", gun=CUMA)),
                     PZT: _gun(PZT, beyan(sembol="KRNT", kisi="A", gun=PZT))})


def test_saturday_daily_and_weekly_as_separate_photos(tmp_path):
    tg = SahteTelegram()
    sonuc = calistir(_ayar(tmp_path, date(2026, 10, 31)), _cuma_sec(), tg.istemci())
    assert sonuc == "gonderildi"
    assert tg.yollar() == ["sendPhoto", "sendPhoto"]
    gunluk, haftalik = tg.aciklamalar()
    assert "INseeder · İçeriden Alımlar · 30.10.2026" in gunluk
    assert "INseeder · Haftanın Özeti · 26–30.10.2026" in haftalik
    assert "parse_mode" not in gunluk
    assert (tmp_path / "cikti" / "haftalik_2026-10-30.png").exists()
    kayit = (tmp_path / "veri" / "gonderilen_kartlar.csv").read_text(encoding="utf-8").splitlines()
    assert kayit[0] == "gun,kart,sayfa,mesaj_id" and len(kayit) == 3


def test_failure_mid_run_resumes_without_resending(tmp_path):
    from rasathane_ortak.tek_gonderim import GonderimHatasi
    tg = SahteTelegram(hatali_foto=2)
    with pytest.raises(GonderimHatasi):
        calistir(_ayar(tmp_path, date(2026, 10, 31)), _cuma_sec(), tg.istemci())
    ikinci = SahteTelegram()
    assert calistir(_ayar(tmp_path, date(2026, 10, 31)), _cuma_sec(), ikinci.istemci()) == "gonderildi"
    assert ikinci.yollar() == ["sendPhoto"]
    assert "Haftanın Özeti" in ikinci.aciklamalar()[0]
    assert calistir(_ayar(tmp_path, date(2026, 10, 31)), _cuma_sec(), SahteTelegram().istemci()) == "zaten_gonderildi"


def test_friday_holiday_weekly_alone(tmp_path):
    noel = date(2026, 12, 25)
    tg = SahteTelegram()
    p1, p2 = date(2026, 12, 21), date(2026, 12, 22)
    sec = SahteSec({noel: _gun(noel, dizin_var=False),
                    p1: _gun(p1, beyan(sembol="AAA", kisi="A", gun=p1)),
                    p2: _gun(p2, beyan(sembol="AAA", kisi="B", gun=p2))})
    sonuc = calistir(_ayar(tmp_path, date(2026, 12, 26)), sec, tg.istemci())
    assert sonuc == "gonderildi"
    assert tg.yollar() == ["sendPhoto"]
    assert not (tmp_path / "cikti" / "gunluk_2026-12-25.png").exists()
    assert (tmp_path / "cikti" / "haftalik_2026-12-25.png").exists()


def test_empty_saturday_sends_nothing(tmp_path):
    tg = SahteTelegram()
    assert calistir(_ayar(tmp_path, date(2026, 10, 31)), SahteSec(), tg.istemci()) == "bos"
    assert tg.istekler == []


def test_empty_day_sends_nothing(tmp_path):
    tg = SahteTelegram()
    sonuc = calistir(_ayar(tmp_path, SALI), SahteSec({PZT: _gun(PZT, beyan(gun=PZT, tutar=5_000))}), tg.istemci())
    assert sonuc == "bos"
    assert tg.istekler == []


def test_backfill_records_missing_days_without_cards(tmp_path):
    sec = SahteSec()
    calistir(_ayar(tmp_path, SALI), sec, SahteTelegram().istemci())
    doldurulan = [c for c in sec.cagrilar if c[0] != PZT]
    assert len(doldurulan) == 7
    assert all(bekle is False for _, bekle in doldurulan)
    assert (PZT, True) in sec.cagrilar
    assert sorted((tmp_path / "cikti").glob("*.png")) == []


def test_backfill_skipped_when_disabled(tmp_path):
    sec = SahteSec()
    calistir(_ayar(tmp_path, SALI, doldur=0), sec, SahteTelegram().istemci())
    assert sec.cagrilar == [(PZT, True)]


def test_backfilled_purchase_creates_cluster(tmp_path, monkeypatch):
    onceki = PZT - timedelta(days=3)  # Cuma
    sec = SahteSec({onceki: _gun(onceki, beyan(sembol="KRNT", kisi="A", gun=onceki)),
                    PZT: _gun(PZT, beyan(sembol="KRNT", kisi="B", gun=PZT))})
    gorulen = []
    asil = calistir_mod.gunluk_kart
    monkeypatch.setattr(calistir_mod, "gunluk_kart", lambda g, s: gorulen.extend(s) or asil(g, s))
    calistir(_ayar(tmp_path, SALI, kuru=True), sec, None)
    assert [s.kume for s in gorulen] == [True]
    aciklama = (tmp_path / "cikti" / "aciklama_2026-10-26.txt").read_text(encoding="utf-8")
    assert aciklama.strip() == "INseeder · İçeriden Alımlar · 26.10.2026"


def _main(tmp_path, monkeypatch, sec, tg, *argv):
    monkeypatch.setenv("SEC_USER_AGENT", "Test test@example.com")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_SAHIP_ID", "99")
    monkeypatch.setenv("TELEGRAM_HEDEF", "@rasathane:42")
    return main(["--veri", str(tmp_path / "veri"), "--cikti", str(tmp_path / "cikti"),
                 "--bugun", "2026-10-27", "--doldur", "0", *argv],
                sec_istemcisi=sec, http_istemcisi=httpx.Client(transport=httpx.MockTransport(tg)))


def test_send_failure_does_not_mark_sent_and_exits_1(tmp_path, monkeypatch):
    tg = SahteTelegram(durum=500)
    kod = _main(tmp_path, monkeypatch, SahteSec({PZT: _gun(PZT, beyan(gun=PZT))}), tg)
    assert kod == 1
    assert "sendMessage" in tg.yollar()
    durum_yolu = tmp_path / "veri" / "gonderilenler.json"
    if durum_yolu.exists():
        assert json.loads(durum_yolu.read_text(encoding="utf-8"))["gunluk"] == []


def test_kanal_error_notifies_owner(tmp_path, monkeypatch):
    tg = SahteTelegram()
    kod = _main(tmp_path, monkeypatch, SahteSec(hata=KanalHatasi("dizin yok")), tg)
    assert kod == 1
    assert tg.yollar() == ["sendMessage"]
    metin = json.loads(tg.istekler[0].content)["text"]
    assert "dizin yok" in metin and "26.10.2026" in metin


def test_main_success_exit_0(tmp_path, monkeypatch):
    tg = SahteTelegram()
    assert _main(tmp_path, monkeypatch, SahteSec({PZT: _gun(PZT, beyan(gun=PZT))}), tg) == 0
    assert tg.yollar() == ["sendPhoto"]


def test_missing_user_agent_exits_2(tmp_path, monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    assert main(["--veri", str(tmp_path), "--kuru"]) == 2


class YarimSec(SahteSec):
    """Doldurma günleri başarılı, anlatılan gün hata verir."""
    def gun_isle(self, gun, bekle_404=True):
        self.cagrilar.append((gun, bekle_404))
        if gun == PZT:
            raise KanalHatasi("dizin yok")
        return _gun(gun, beyan(sembol="KRNT", gun=gun))


def test_backfill_saved_even_if_target_day_fails(tmp_path):
    with pytest.raises(KanalHatasi):
        calistir(_ayar(tmp_path, SALI), YarimSec(), SahteTelegram().istemci())
    durum = json.loads((tmp_path / "veri" / "gonderilenler.json").read_text(encoding="utf-8"))
    assert len(durum["islenen"]) == 7
    assert "2026-10-26" not in durum["islenen"]


def test_target_without_token_exits_1(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test test@example.com")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_HEDEF", "@rasathane:42")
    kod = main(["--veri", str(tmp_path / "veri"), "--cikti", str(tmp_path / "c"), "--bugun", "2026-10-27",
                "--doldur", "0"], sec_istemcisi=SahteSec({PZT: _gun(PZT, beyan(gun=PZT))}))
    assert kod == 1


def test_httpx_request_logs_silenced(tmp_path, monkeypatch):
    import logging
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.NOTSET)
    _main(tmp_path, monkeypatch, SahteSec(), SahteTelegram())
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def _fiyat_cekici(son=10.0):
    def cek(sembol, bas, son_gun):
        n = (son_gun - bas).days
        return [(bas + timedelta(days=i), son + (i % 3) * 0.1) for i in range(n)]
    return cek


def test_grafik_after_daily_before_weekly(tmp_path):
    tg = SahteTelegram()
    sonuc = calistir(_ayar(tmp_path, date(2026, 10, 31)), _cuma_sec(), tg.istemci(), fiyat_cekici=_fiyat_cekici())
    assert sonuc == "gonderildi"
    ad = [a for a in tg.aciklamalar()]
    assert "İçeriden Alımlar" in ad[0]
    assert "INseeder · Fiyat Grafiği · 30.10.2026" in ad[1]
    assert "Haftanın Özeti" in ad[2]
    assert (tmp_path / "cikti" / "grafik_2026-10-30.png").exists()


def test_fiyat_yoksa_grafik_atlanir(tmp_path):
    def bozuk(sembol, bas, son):
        raise RuntimeError("Yahoo kapalı")

    tg = SahteTelegram()
    sonuc = calistir(_ayar(tmp_path, SALI), SahteSec({PZT: _gun(PZT, beyan(gun=PZT))}), tg.istemci(),
                     fiyat_cekici=bozuk)
    assert sonuc == "gonderildi"
    assert sorted(tg.yollar()) == ["sendMessage", "sendPhoto"]
    assert "Fiyat Grafiği" not in tg.aciklamalar()[0]
    bildirim = next(r for r in tg.istekler if "sendMessage" in r.url.path)
    assert "Yahoo kapalı" in json.loads(bildirim.content)["text"]


def test_grafik_yok_gunluk_yoksa(tmp_path):
    cagri = []
    calistir(_ayar(tmp_path, SALI), SahteSec(), SahteTelegram().istemci(),
             fiyat_cekici=lambda *a: cagri.append(a) or [])
    assert cagri == []
