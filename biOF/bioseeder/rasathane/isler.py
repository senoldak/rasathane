import csv
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple

from bioseeder.rasathane import ctgov, edgar
from bioseeder.rasathane.ayar import EK
from bioseeder.rasathane.ctgov import Calisma, fark, goruntu_oku, goruntu_yaz, yaklasanlar
from bioseeder.rasathane.edgar import Bildirim
from bioseeder.rasathane.grafik import AD as GRAFIK_AD
from bioseeder.rasathane.grafik import GUN_SAYISI, FiyatCekici, olay_grafigi
from bioseeder.rasathane.evren import (
    Sirket, ek_uygula, evren_oku, evren_olustur, evren_yaz, sponsor_eslestir, yahoo_piyasa_degeri,
)
from bioseeder.rasathane.http import Istemci, KaynakHatasi
from bioseeder.rasathane.kart import FIKIR, KART_BASINA, calisma_kutucugu, kart, olay_kutucugu
from bioseeder.rasathane.kayit import Kayit
from bioseeder.rasathane.olay import Olay, buyuk_mu, sirala
from bioseeder.rasathane.siniflandir import siniflandir
from bioseeder.rasathane.takvim import edgar_acik_mi, is_gunleri, onceki_is_gunu
from rasathane_ortak import kagit
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi

AZAMI_GUN_OLAY = 150
AZAMI_TELAFI_GUN = 5
AZAMI_GUN_ICI = 2
HAFTALIK_KUTUCUK = 18
ASGARI_PIST_ORANI = 0.7
ASGARI_EVREN = 100
SABAH_AD = "Sabah Bülteni"
HAFTALIK_AD = "Önümüzdeki 60 Gün"
GUN_ICI_AD = "Büyük Olay"
SABAH_BASLIK = "Günün faz ve FDA değişiklikleri"
HAFTALIK_BASLIK = "Bitişi beklenen Faz 2/3 çalışmaları"
HAFTALIK_NOT = "Tarihler şirketin ClinicalTrials.gov tahminidir; sonuç açıklama tarihi değildir."
_NCT = re.compile(r"NCT\d{8}")


class GercekKaynaklar:
    """Ağa çıkan kaynaklar; testlerde aynı yöntemleri taşıyan sahte nesneyle değiştirilir."""

    def __init__(self, ist: Istemci, veri: Path, bugun: date):
        self.ist = ist
        self.veri = veri
        self.bugun = bugun

    def evren(self) -> Tuple[List[Sirket], Dict[str, str]]:
        return ek_uygula(evren_oku(self.veri / "evren.csv", self.bugun), EK)

    def evren_olustur(self) -> List[Sirket]:
        try:
            eski = {s.cik: s.sic for s in evren_oku(self.veri / "evren.csv", date.min + timedelta(days=1))}
        except KaynakHatasi:
            eski = {}
        return evren_olustur(self.ist, yahoo_piyasa_degeri, eski)

    def ctgov_guncel(self, gun: date, sponsorlar: Mapping[str, Sirket], eslesmeyen: Set[str]) -> List[Calisma]:
        return ctgov.calismalari_cek(self.ist, ctgov.sorgu(gun), sponsorlar, eslesmeyen)

    def ctgov_tum(self, sponsorlar: Mapping[str, Sirket], eslesmeyen: Set[str]) -> List[Calisma]:
        return ctgov.calismalari_cek(self.ist, ctgov.sorgu(None), sponsorlar, eslesmeyen)

    def edgar_gunluk(self, gun: date) -> List[Bildirim]:
        return edgar.gunluk_8k(self.ist, gun)

    def edgar_guncel(self, imlec: Optional[str]) -> Tuple[List[Bildirim], Optional[str]]:
        return edgar.guncel_8k(self.ist, imlec)

    def bulten(self, b: Bildirim) -> str:
        return edgar.bulten_metni(self.ist, b)

    def nakit_pisti(self, ticker: str) -> Optional[float]:
        from bioseeder.collectors.market_data import MarketDataCollector

        pist = MarketDataCollector().fetch_ticker_overview(ticker).get("cash_runway_months")
        return float(pist) if pist is not None else None


@dataclass
class Baglam:
    kaynak: Any
    telegram: Any
    kuru: bool
    bugun: date  # İstanbul tarihi
    veri: Path
    cikti: Path
    gonderim_acik: bool = False
    fiyat_cekici: Optional[FiyatCekici] = None  # None: Olay Grafiği kapalı

    @property
    def kayit_yolu(self) -> Path:
        return self.veri / "gonderilen.json"


def _gidenler(anahtar: Callable[[Tuple[int, ...]], str], k: "kagit.Kart") -> List[Giden]:
    """Kartı sayfalara böler; her sayfanın kayıt anahtarı sayfadaki satırlardan türetilir."""
    return [Giden(anahtar(sf.satirlar), sf.no, sf.png, kagit.mesaj_metni(FIKIR, k.ad, k.tarih, sf.no, sf.toplam))
            for sf in kagit.ciz(k, sayfa_basina=KART_BASINA)]


def _olay_grafigi(b: Baglam, o: Olay, sirketler: List[Sirket], tarih_metni: str) -> Optional[Giden]:
    """Bültenin en önemli olayının fiyat grafiği; çizilemezse atlanır ve sahibine bildirilir."""
    if b.fiyat_cekici is None:
        return None
    try:
        sirket = next((s.ad for s in sirketler if s.ticker == o.ticker), "")
        fiyat = b.fiyat_cekici(o.ticker, o.tarih - timedelta(days=GUN_SAYISI + 10), o.tarih + timedelta(days=1))
        png = kagit.grafik_ciz(olay_grafigi(o, sirket, tarih_metni, fiyat))
    except Exception as exc:  # noqa: BLE001 — grafik yalnız ektir, bülten yine gider
        if not b.kuru:
            b.telegram.sahibe(f"biOF Olay Grafiği atlandı ({o.ticker}): {type(exc).__name__}: {exc}")
        return None
    return Giden(f"grafik:{o.kimlik}", 1, png, kagit.mesaj_metni(FIKIR, GRAFIK_AD, tarih_metni))


def _gonder(b: Baglam, is_adi: str, gun: str, gidenler: List[Giden],
            sonrasi: Optional[Callable[[Giden, int], None]] = None) -> None:
    if b.kuru:
        b.cikti.mkdir(parents=True, exist_ok=True)
        for g in gidenler:
            (b.cikti / f"{is_adi}-{gun}-{g.sayfa}.png").write_bytes(g.png)
        (b.cikti / f"{is_adi}-{gun}.txt").write_text("\n".join(g.aciklama for g in gidenler), encoding="utf-8")
        return
    b.telegram.sirayla(gun, gidenler, GonderimKaydi(b.veri / "gonderilen_kartlar.csv"), sonrasi=sonrasi)


def _eslesmeyen_yaz(veri: Path, eslesmeyen: Set[str], gun: date) -> None:
    yol = veri / "eslesmeyen_sponsorlar.csv"
    mevcut: Dict[str, str] = {}
    if yol.exists():
        with yol.open(encoding="utf-8", newline="") as f:
            mevcut = {r["sponsor"]: r["ilk_gorulme"] for r in csv.DictReader(f)}
    for ad in eslesmeyen:
        mevcut.setdefault(ad, gun.isoformat())
    with yol.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sponsor", "ilk_gorulme"])
        for ad in sorted(mevcut):
            w.writerow([ad, mevcut[ad]])


def _bildirim_olayi(bl: Bildirim, metin: str, sirket: Sirket, goruntu: Mapping[str, Calisma]) -> Optional[Olay]:
    sonuc = siniflandir(metin)
    if sonuc is None:
        return None
    tur, faz3 = sonuc
    satir = "Ayrıntı: 8-K basın bülteni"
    for nct in _NCT.findall(metin):
        if nct in goruntu:
            satir = f"{goruntu[nct].ilac} · {goruntu[nct].hastalik}"
            break
    return Olay(kimlik=bl.erisim, tur=tur, ticker=sirket.ticker, satir=satir,
                ayrinti=f"SEC 8-K · {bl.tarih:%d.%m.%Y}", tarih=bl.tarih, faz3=faz3, mikro=sirket.mikro,
                baglanti=bl.baglanti)


def _bulten(b: Baglam, bl: Bildirim) -> str:
    """Tek bir bildirimin dosyası yoksa (404) atlanır; diğer hatalar işi durdurur."""
    try:
        return b.kaynak.bulten(bl)
    except KaynakHatasi as exc:
        if exc.durum == 404:
            print(f"Bülten okunamadı, atlandı: {bl.erisim}", file=sys.stderr)
            return ""
        raise


def _tarih_metni(gunler: List[date]) -> str:
    if len(gunler) == 1:
        return f"{gunler[0]:%d.%m.%Y}"
    return f"{gunler[0]:%d.%m}–{gunler[-1]:%d.%m.%Y}"


def evren_isi(b: Baglam) -> int:
    sirketler = b.kaynak.evren_olustur()
    if len(sirketler) < ASGARI_EVREN:
        raise KaynakHatasi(f"Evren olağandışı küçük ({len(sirketler)} şirket); yazılmadı")
    evren_yaz(sirketler, b.veri / "evren.csv", b.bugun)
    return 0


def ilk_kurulum_isi(b: Baglam) -> int:
    sirketler, esle = b.kaynak.evren()
    eslesmeyen: Set[str] = set()
    tum = b.kaynak.ctgov_tum(sponsor_eslestir(sirketler, esle), eslesmeyen)
    goruntu_yaz({c.nct: c for c in tum}, b.veri / "ctgov.csv")
    _eslesmeyen_yaz(b.veri, eslesmeyen, b.bugun)
    return 0


def sabah_isi(b: Baglam, tarih: Optional[date] = None) -> int:
    sirketler, esle = b.kaynak.evren()
    sponsorlar = sponsor_eslestir(sirketler, esle)
    cikten = {s.cik: s for s in sirketler}
    mikro = {s.ticker: s.mikro for s in sirketler}
    kayit = Kayit.oku(b.kayit_yolu)
    goruntu = goruntu_oku(b.veri / "ctgov.csv")
    if not goruntu:
        raise KaynakHatasi("ClinicalTrials.gov görüntüsü yok; önce 'ilk-kurulum' işini çalıştırın")

    son = onceki_is_gunu(b.bugun)
    if tarih:
        gunler = [tarih]
    elif kayit.son_sabah_gunu:
        gunler = is_gunleri(kayit.son_sabah_gunu + timedelta(days=1), son)[-AZAMI_TELAFI_GUN:]
    else:
        gunler = [son]
    if not gunler:
        return 0

    eslesmeyen: Set[str] = set()
    olaylar: List[Olay] = []
    for gun in gunler:
        yeni = b.kaynak.ctgov_guncel(gun, sponsorlar, eslesmeyen)
        gunun = fark(goruntu, yeni, gun, mikro)
        goruntu.update({c.nct: c for c in yeni})
        # Federal tatilde EDGAR kapalıdır, günlük dizin oluşmaz; iş günündeki eksik dizin ise hatadır.
        bildirimler = b.kaynak.edgar_gunluk(gun) if edgar_acik_mi(gun) else []
        for bl in bildirimler:
            sirket = cikten.get(bl.cik)
            if sirket:
                o = _bildirim_olayi(bl, _bulten(b, bl), sirket, goruntu)
                if o:
                    gunun.append(o)
        if len(gunun) > AZAMI_GUN_OLAY:
            raise KaynakHatasi(f"Olağandışı olay sayısı ({len(gunun)}, {gun.isoformat()}); veri bozuk olabilir")
        olaylar.extend(o for o in gunun if not kayit.gonderildi_mi(o.kimlik))

    gidenler: List[Giden] = []
    if olaylar:
        olaylar = sirala(olaylar)
        k = kart(SABAH_AD, _tarih_metni(gunler), [olay_kutucugu(o) for o in olaylar], SABAH_BASLIK)
        sayfa_olaylari: Dict[Tuple[str, int], List[Olay]] = {}

        def anahtar(satirlar: Tuple[int, ...]) -> str:
            # Sayfanın ilk olayına bağlı: yarıda kalan koşuda kalan olaylar yeni sayfalara dizilir.
            return f"sabah:{olaylar[satirlar[0]].kimlik}"

        gidenler = _gidenler(anahtar, k)
        for g, sf in zip(gidenler, kagit.ciz(k, sayfa_basina=KART_BASINA)):
            sayfa_olaylari[(g.kart, g.sayfa)] = [olaylar[i] for i in sf.satirlar]

        def sayfa_gitti(g: Giden, _mesaj_id: int) -> None:
            kayit.isaretle(o.kimlik for o in sayfa_olaylari[(g.kart, g.sayfa)])
            kayit.yaz(b.kayit_yolu)

        _gonder(b, "sabah", gunler[-1].isoformat(), gidenler, sonrasi=sayfa_gitti)
        grafik = _olay_grafigi(b, olaylar[0], sirketler, k.tarih)
        if grafik:
            try:
                _gonder(b, "sabah-grafik", gunler[-1].isoformat(), [grafik])
            except Exception as exc:  # noqa: BLE001 — bülten gitti; grafik yüzünden günün durumu kaybolmasın
                b.telegram.sahibe(f"biOF Olay Grafiği gönderilemedi ({olaylar[0].ticker}): {exc}")

    # Görüntü yalnız gönderim (ya da kuru çıktı) başarılı olduktan sonra yazılır. Gönderim açıkken kuru
    # bir önizleme görüntüyü ilerletmez; yoksa o günün olayları asıl koşuda kaybolurdu.
    if not (b.kuru and b.gonderim_acik):
        goruntu_yaz(goruntu, b.veri / "ctgov.csv")
    _eslesmeyen_yaz(b.veri, eslesmeyen, b.bugun)
    if not b.kuru:
        kayit.son_sabah_gunu = gunler[-1]
        kayit.yaz(b.kayit_yolu)
    return len(gidenler)


def haftalik_isi(b: Baglam) -> int:
    kayit = Kayit.oku(b.kayit_yolu)
    if b.bugun in kayit.haftalik:
        return 0
    sirketler, _ = b.kaynak.evren()
    mikro = {s.ticker: s.mikro for s in sirketler}
    liste = yaklasanlar(goruntu_oku(b.veri / "ctgov.csv"), b.bugun)[:HAFTALIK_KUTUCUK]
    gidenler: List[Giden] = []
    if liste:
        pist = {t: b.kaynak.nakit_pisti(t) for t in {c.ticker for c in liste}}
        okunan = sum(1 for v in pist.values() if v is not None)
        if okunan < ASGARI_PIST_ORANI * len(pist):
            raise KaynakHatasi(f"Nakit pisti yalnız {okunan}/{len(pist)} şirkette okunabildi")
        kutucuklar = [calisma_kutucugu(c, b.bugun, pist[c.ticker], mikro.get(c.ticker, True)) for c in liste]
        k = kart(HAFTALIK_AD, kagit.tarih_metni(b.bugun), kutucuklar, HAFTALIK_BASLIK, not_=HAFTALIK_NOT,
                 kaynak="ClinicalTrials.gov · Yahoo Finance")
        gidenler = _gidenler(lambda _: "haftalik", k)
        _gonder(b, "haftalik", b.bugun.isoformat(), gidenler)
    if not b.kuru:
        kayit.haftalik.append(b.bugun)
        kayit.yaz(b.kayit_yolu)
    return len(gidenler)


def gun_ici_isi(b: Baglam) -> int:
    sirketler, _ = b.kaynak.evren()
    cikten = {s.cik: s for s in sirketler}
    kayit = Kayit.oku(b.kayit_yolu)
    goruntu = goruntu_oku(b.veri / "ctgov.csv")
    bildirimler, imlec = b.kaynak.edgar_guncel(kayit.edgar_imlec)
    adaylar: List[Olay] = []
    for bl in bildirimler:
        sirket = cikten.get(bl.cik)
        # Gün içi kimliği ayrı tutulur: aynı olay ertesi sabahın özetinde yine yer alır.
        if not sirket or kayit.gonderildi_mi(f"gi:{bl.erisim}"):
            continue
        o = _bildirim_olayi(bl, _bulten(b, bl), sirket, goruntu)
        if o and buyuk_mu(o):
            adaylar.append(o)
    gonderilen = 0
    for o in sirala(adaylar):
        if kayit.gun_ici_sayisi(b.bugun) + (gonderilen if b.kuru else 0) >= AZAMI_GUN_ICI:
            break
        k = kart(GUN_ICI_AD, kagit.tarih_metni(o.tarih), [olay_kutucugu(o)], "Gün içinde SEC'e bildirilen büyük olay",
                 kaynak="SEC EDGAR")
        _gonder(b, "gun-ici", o.tarih.isoformat(), _gidenler(lambda _: f"gun-ici:{o.kimlik}", k))
        gonderilen += 1
        if not b.kuru:
            kayit.isaretle([f"gi:{o.kimlik}"])
            kayit.gun_ici_artir(b.bugun)
            kayit.yaz(b.kayit_yolu)
    if not b.kuru:
        kayit.edgar_imlec = imlec
        kayit.yaz(b.kayit_yolu)
    return gonderilen


def calistir(is_adi: str, fn: Callable[[], int], b: Baglam) -> int:
    try:
        sayi = fn()
    except Exception as exc:  # noqa: BLE001 — her hata sahibine bildirilir, hiçbir şey yayımlanmaz
        mesaj = f"biOF Rasathane '{is_adi}' hatası: {type(exc).__name__}: {exc}"
        print(mesaj, file=sys.stderr)
        if not b.kuru:
            try:
                b.telegram.sahibe(mesaj)
            except Exception as bildirim_hatasi:  # noqa: BLE001
                print(f"Sahibe bildirim gönderilemedi: {bildirim_hatasi}", file=sys.stderr)
        return 1
    print(f"biOF Rasathane '{is_adi}': {sayi} kart" + (" (kuru)" if b.kuru else ""))
    return 0
