"""FX günlük akışı: kurlar → ölçüm ve sinyaller → haftalık/aylık analizler → kartlar → gönderim.

Her işlem günü: FX Panosu, Risk Panosu, sinyal türü başına liste (4 ve üstünde) ve her sinyal
için grafik; kur bağı kırılırsa korelasyon grafiği; politika faizi değişirse Faiz Kararı; Fed
vadelilerinde bir ay 10 bp'den fazla oynarsa Fed Beklentisi.
Haftanın ilk işlem günü: Carry Tablosu, Faiz Farkı ve Kur, Fed Beklentisi, Kur Bağları, Kur
Oynaklığı, Seanslara Göre Hareket, Sinyal Karnesi. CFTC kartı yeni rapor haftasında bir kez.
Ayın ilk işlem günü: Kura Duyarlı Hisseler.
Zirve, dip, oynaklık ve bağ sinyali aynı kur için 10 işlem günü içinde tekrarlanmaz.

Ayarlar ortamdan: TELEGRAM_BOT_TOKEN, TELEGRAM_HEDEF (@grup:konu), TELEGRAM_SAHIP_ID.
"""

import csv
import datetime
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from rasathane_ortak import kagit
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi, sirayla_gonder

from . import analiz, raporlar, veri
from .cizim import (
    FIKIR,
    SAYFA_SATIRI,
    bag_grafigi,
    baglar_ciz,
    carry_ciz,
    cot_ciz,
    duyarlilik_ciz,
    etiket,
    faiz_farki_ciz,
    faiz_karari_ciz,
    fed_ciz,
    karne_ciz,
    oynaklik_ciz,
    pano_ciz,
    risk_ciz,
    seans_ciz,
    sinyal_grafigi,
    sinyal_listesi_ciz,
)
from .evren import BIST100, KURLAR, SEPET, TUM_SEMBOLLER, USDTRY
from .tarama import TURLER, Olcum, Sinyal, olc, sepet, sinyaller

_MIN_ORAN = 0.80  # kurların bu kadarında bugünün verisi yoksa gönderim yok
_LISTE_ESIGI = 4
_SUSTURMA_GUN = 10
_SUSTURULAN = {"zirve_52", "dip_52", "oynaklik", "bag"}
_FED_ESIK = 10.0  # bp
_ARA = 3.2  # Telegram grup sınırı ~20 mesaj/dk
_NY = ZoneInfo("America/New_York")
_ANA = "EURUSD=X"
_SEANS_KURLARI = ["EURUSD=X", "JPY=X", "GBPUSD=X", "AUDUSD=X", "CAD=X", "CHF=X", USDTRY]

log = logging.getLogger("fx")


class Sonuc(TypedDict):
    durum: Literal["islem_yok", "eksik_veri", "zaten_gonderildi", "kart_yok", "kuru", "gonderildi"]
    kart_sayisi: int


Indirici = Callable[[list[str]], dict[str, pd.DataFrame]]


def _saatlik(semboller: list[str]) -> dict[str, pd.DataFrame]:
    return veri.indir(semboller, donem="10d", aralik="60m")


def _hisseler(bugun: datetime.date) -> dict[str, pd.DataFrame]:
    return veri.indir([*raporlar.bist_evreni(bugun), BIST100], donem="2y")


def _tahviller() -> dict[str, pd.Series]:
    return {"ABD": raporlar.abd_2y(), "EUR": raporlar.euro_2y(), "JPY": raporlar.japonya_2y()}


def _cot() -> list[raporlar.Pozisyon]:
    pozisyonlar = []
    for kod, para in raporlar.COT_KODLARI:
        try:
            pozisyonlar.append(raporlar.cot(kod, para))
        except Exception as e:
            log.warning("CFTC %s alınamadı: %s", para, e)
    if not pozisyonlar:
        return []
    son = max(p.donem for p in pozisyonlar)
    return [p for p in pozisyonlar if p.donem == son]


@dataclass
class Kaynaklar:
    indir: Indirici = veri.indir
    saatlik: Indirici = _saatlik
    hisseler: Callable[[datetime.date], dict[str, pd.DataFrame]] = _hisseler
    faizler: Callable[[], dict[str, float]] = raporlar.politika_faizleri
    tahviller: Callable[[], dict[str, pd.Series]] = _tahviller
    cot: Callable[[], list[raporlar.Pozisyon]] = _cot
    hatalar: list[str] = field(default_factory=list)

    def dene(self, ad_: str, f: Callable[[], Any]) -> Any:
        """Bir kaynak düşerse akış sürer; düşenler sahibe tek mesajda bildirilir."""
        try:
            return f()
        except Exception as e:
            log.warning("%s alınamadı: %s", ad_, e)
            self.hatalar.append(f"{ad_}: {type(e).__name__}")
            return None


def _sahibe(metin: str) -> None:
    token, sahip = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_SAHIP_ID")
    if not (token and sahip):
        log.error("sahibe yazılamadı (token/sahip yok): %s", metin)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": sahip, "text": metin},
            timeout=30,
        )
    except Exception as e:
        log.error("sahibe bildirim gönderilemedi: %s", type(e).__name__)


def requests_istek(
    url: str, alanlar: dict[str, str], dosyalar: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    y = requests.post(url, data=alanlar, files=dosyalar or None, timeout=60)
    try:
        govde: dict[str, Any] = y.json()
    except ValueError:
        govde = {}
    return y.status_code, govde


def _json_oku(yol: Path) -> dict[str, Any]:
    if not yol.exists():
        return {}
    veri_: dict[str, Any] = json.loads(yol.read_text(encoding="utf-8"))
    return veri_


def _json_yaz(yol: Path, veri_: dict[str, Any]) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri_, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")


def _kayit_oku(yol: Path) -> list[dict[str, str]]:
    if not yol.exists():
        return []
    with open(yol, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _susturulanlar(
    kayit: list[dict[str, str]], tarih: str, gunler: list[str]
) -> set[tuple[str, str]]:
    once = [g for g in gunler if g < tarih][-_SUSTURMA_GUN:]
    sinir = once[0] if once else tarih
    return {(r["tur"], r["sembol"]) for r in kayit if sinir <= r["tarih"] < tarih}


def _kaydet(yol: Path, tarih: str, ciftler: list[tuple[str, str]]) -> None:
    yeni = not yol.exists()
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if yeni:
            w.writerow(["tarih", "tur", "sembol"])
        for tur, sembol in ciftler:
            w.writerow([tarih, tur, sembol])


def _ilk_mi(tarih: str, gunler: list[str], aylik: bool = False) -> bool:
    d = datetime.date.fromisoformat(tarih)
    bas = d.replace(day=1) if aylik else d - datetime.timedelta(days=d.weekday())
    return not any(bas.isoformat() <= g < tarih for g in gunler)


def calistir(
    kuru: bool,
    tarih: str | None = None,
    cikti: Path = Path("cikti"),
    simdi: datetime.datetime | None = None,
    veri_dizini: Path = Path("veri"),
    kaynaklar: Kaynaklar | None = None,
) -> Sonuc:
    k = kaynaklar or Kaynaklar()
    simdi = simdi or datetime.datetime.now(datetime.timezone.utc)
    bugun_ny = simdi.astimezone(_NY).date()
    zq = analiz.zq_sembolleri(bugun_ny)
    # Yahoo ertesi günün kur satırını 00:00 UTC'de açar; New York'ta henüz gelmemiş günler atılır
    yarin = pd.Timestamp(bugun_ny + datetime.timedelta(days=1))
    tablolar = {
        s: df[pd.DatetimeIndex(df.index).tz_localize(None) < yarin]
        for s, df in k.indir([*TUM_SEMBOLLER, *(s for s, _ in zq)]).items()
    }
    tablolar = {s: df for s, df in tablolar.items() if len(df)}
    if _ANA not in tablolar:
        _sahibe("FX: Yahoo'dan EUR/USD verisi alınamadı, gönderim yok.")
        return {"durum": "eksik_veri", "kart_sayisi": 0}
    gunler = [g.date().isoformat() for g in pd.DatetimeIndex(tablolar[_ANA].index)]
    if tarih is None:
        tarih = gunler[-1]
        if tarih != bugun_ny.isoformat():
            return {"durum": "islem_yok", "kart_sayisi": 0}
    elif tarih != gunler[-1]:
        raise ValueError(f"yalnız son seans ({gunler[-1]}) üretilebilir: {tarih}")

    durum_yolu = veri_dizini / "durum.json"
    durum = _json_oku(durum_yolu)
    if not kuru and tarih in durum.get("gunler", []):
        return {"durum": "zaten_gonderildi", "kart_sayisi": 0}

    def bugunku_mu(df: pd.DataFrame) -> bool:
        return bool(pd.DatetimeIndex(df.index)[-1].date().isoformat() == tarih)

    bugunku = {s: df for s, df in tablolar.items() if bugunku_mu(df)}
    kur_sayisi = sum(x.sembol in bugunku for x in KURLAR)
    if kur_sayisi < _MIN_ORAN * len(KURLAR):
        _sahibe(f"FX {tarih}: yalnız {kur_sayisi}/{len(KURLAR)} kurda bugünün verisi var.")
        return {"durum": "eksik_veri", "kart_sayisi": 0}

    olcumler: dict[str, Olcum] = {}
    bulunan: list[Sinyal] = []
    kur_tablolari = {x.sembol: bugunku[x.sembol] for x in KURLAR if x.sembol in bugunku}
    sp = sepet(tablolar)
    if sp is not None and bugunku_mu(sp):
        kur_tablolari[SEPET] = sp
    for sembol, df in kur_tablolari.items():
        try:
            o = olc(sembol, df)
        except Exception as e:
            log.warning("%s ölçülemedi: %s", sembol, e)
            continue
        if o is None:
            continue
        olcumler[sembol] = o
        bulunan.extend(sinyaller(sembol, df, o))

    sinyal_yolu = veri_dizini / "sinyal_kaydi.csv"
    kayit = _kayit_oku(sinyal_yolu)
    susturulan = _susturulanlar(kayit, tarih, gunler)
    kaydedilecek: list[tuple[str, str]] = []
    kartlar: list[tuple[str, kagit.Kart]] = []
    grafikler: list[tuple[str, kagit.Grafik, str]] = []
    gun_tarihi = kagit.tarih_metni(datetime.date.fromisoformat(tarih))
    haftalik = _ilk_mi(tarih, gunler)
    yeni_durum: dict[str, Any] = {}

    kartlar.append(("pano", pano_ciz(olcumler, olcumler.get(SEPET), tarih)))
    r = analiz.risk(tablolar)
    if r is not None:
        kartlar.append(("risk", risk_ciz(r, tarih)))

    faizler: dict[str, float] = k.dene("BIS faizleri", k.faizler) or {}
    if faizler:
        eski: dict[str, float] = durum.get("faizler", {})
        degisen = [
            (p, eski[p], f) for p, f in sorted(faizler.items()) if p in eski and eski[p] != f
        ]
        if degisen:
            kartlar.append((f"faiz_karari:{tarih}", faiz_karari_ciz(degisen, tarih)))
        yeni_durum["faizler"] = {**eski, **faizler}

    abd = faizler.get("USD")
    beklentiler = analiz.fed_beklentisi(tablolar, bugun_ny, abd) if abd is not None else []
    if haftalik and beklentiler:
        kartlar.append(("fed", fed_ciz(beklentiler, abd or 0.0, tarih, "Fed Beklentisi")))
    elif any(b.degisim is not None and abs(b.degisim) >= _FED_ESIK for b in beklentiler):
        kartlar.append(("fed", fed_ciz(beklentiler, abd or 0.0, tarih, "Fed Beklentisi Değişti")))

    if haftalik:
        if faizler and abd is not None:
            kartlar.append(("carry", carry_ciz(analiz.carry(faizler, tablolar), abd, tarih)))
        tahvil: dict[str, pd.Series] | None = k.dene("tahvil faizleri", k.tahviller)
        if tahvil:
            farklar = [
                f
                for f in (
                    analiz.faiz_farki(
                        "ABD – Euro", "EURUSD=X", tahvil["ABD"], tahvil["EUR"], tablolar
                    ),
                    analiz.faiz_farki(
                        "ABD – Japonya", "JPY=X", tahvil["ABD"], tahvil["JPY"], tablolar
                    ),
                )
                if f is not None
            ]
            if farklar:
                kartlar.append(("faiz_farki", faiz_farki_ciz(farklar, tarih)))
        bag_olcumleri = analiz.baglar(tablolar)
        if bag_olcumleri:
            kartlar.append(("baglar", baglar_ciz(bag_olcumleri, tarih)))
        oyn = analiz.oynakliklar(tablolar, [x.sembol for x in KURLAR])
        if oyn:
            kartlar.append(("oynaklik", oynaklik_ciz(oyn, tarih)))
        saatlik = k.dene("saatlik kurlar", lambda: k.saatlik(_SEANS_KURLARI))
        if saatlik:
            kartlar.append(("seans", seans_ciz(analiz.seanslar(saatlik), tarih)))
        karneler = analiz.karne(kayit, {**tablolar, **kur_tablolari})
        if karneler:
            kartlar.append(("karne", karne_ciz(karneler, tarih)))
    else:
        bag_olcumleri = analiz.baglar(tablolar)

    if _ilk_mi(tarih, gunler, aylik=True) and USDTRY in tablolar:
        hisseler = k.dene("BIST hisseleri", lambda: k.hisseler(bugun_ny))
        if hisseler and BIST100 in hisseler:
            d = analiz.duyarliliklar(
                {s: df for s, df in hisseler.items() if s != BIST100},
                tablolar[USDTRY],
                hisseler[BIST100],
            )
            if len(d) >= 10:
                kartlar.append(("duyarlilik", duyarlilik_ciz(d, tarih)))

    for b in bag_olcumleri:
        if b.kirildi and ("bag", b.bag.anahtar) not in susturulan:
            grafikler.append(
                (f"grafik:bag:{b.bag.anahtar}", bag_grafigi(b, tarih), f"{b.bag.ad} | {gun_tarihi}")
            )
            kaydedilecek.append(("bag", b.bag.anahtar))

    for tur in TURLER:
        turunkiler = sorted(
            (
                s
                for s in bulunan
                if s.tur == tur and not (tur in _SUSTURULAN and (tur, s.sembol) in susturulan)
            ),
            key=lambda s: -abs(s.gunluk),
        )
        if not turunkiler:
            continue
        if len(turunkiler) >= _LISTE_ESIGI:
            kartlar.append((f"liste:{tur}", sinyal_listesi_ciz(tur, turunkiler, tarih)))
        for sy in turunkiler:
            try:
                gr = sinyal_grafigi(sy, kur_tablolari[sy.sembol], tarih)
            except Exception as e:
                log.warning("%s grafiği çizilemedi: %s", sy.sembol, e)
                continue
            aciklama = f"{etiket(sy.sembol)} | {TURLER[tur]} | {gun_tarihi}"
            grafikler.append((f"grafik:{tur}:{sy.sembol}", gr, aciklama))
            kaydedilecek.append((tur, sy.sembol))

    son_cot = dict(durum.get("raporlar", {})).get("cot", "")
    pozisyonlar: list[raporlar.Pozisyon] = k.dene("CFTC", k.cot) or []
    if pozisyonlar and pozisyonlar[0].donem > son_cot:
        kartlar.append((f"cot:{pozisyonlar[0].donem}", cot_ciz(pozisyonlar)))
        yeni_durum["raporlar"] = {"cot": pozisyonlar[0].donem}

    gidenler: list[Giden] = []
    for anahtar, kart in kartlar:
        for sf in kagit.ciz(kart, sayfa_basina=SAYFA_SATIRI):
            gidenler.append(
                Giden(
                    anahtar,
                    sf.no,
                    sf.png,
                    kagit.mesaj_metni(FIKIR, kart.ad, kart.tarih, sf.no, sf.toplam),
                )
            )
    for anahtar, gr, aciklama in grafikler:
        gidenler.append(Giden(anahtar, 1, kagit.grafik_ciz(gr), aciklama))

    cikti.mkdir(parents=True, exist_ok=True)
    for i, g in enumerate(gidenler):
        (cikti / f"{tarih}_{i:03d}.png").write_bytes(g.png)
    if kuru:
        return {"durum": "kuru" if gidenler else "kart_yok", "kart_sayisi": len(gidenler)}

    if k.hatalar:
        _sahibe(f"FX {tarih}: alınamayan kaynaklar: " + ", ".join(k.hatalar))
    try:
        sirayla_gonder(
            requests_istek,
            os.environ["TELEGRAM_BOT_TOKEN"],
            os.environ["TELEGRAM_HEDEF"],
            tarih,
            gidenler,
            GonderimKaydi(veri_dizini / "gonderilen_kartlar.csv"),
            ara=_ARA,
        )
    except Exception as e:
        _sahibe(f"FX {tarih}: gönderim başarısız (giden kartlar kaydedildi): {e}")
        raise
    _kaydet(sinyal_yolu, tarih, kaydedilecek)
    durum.update(yeni_durum)
    durum["gunler"] = sorted({*durum.get("gunler", []), tarih})[-60:]
    _json_yaz(durum_yolu, durum)
    return {"durum": "gonderildi", "kart_sayisi": len(gidenler)}
