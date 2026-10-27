"""Emtia günlük akışı: vadeli fiyatlar → ölçüm ve sinyaller → haftalık raporlar → kartlar → gönderim.

Her işlem günü: Emtia Panosu, Emtia Oranları, sinyal türü başına liste (4 ve üstünde) ve her
sinyal için grafik; oran uç dilimdeyse oran grafiği; gram altın 5 yılın zirvesindeyse grafik.
Haftanın ilk işlem günü: Haftanın Veri Takvimi. EIA ve CFTC kartları yeni rapor haftası
yayımlandığında (genelde Çarşamba, Perşembe, Cuma) bir kez gider.
Zirve, dip, oran ve gram altın sinyali aynı emtia için 10 işlem günü içinde tekrarlanmaz.

Ayarlar ortamdan: TELEGRAM_BOT_TOKEN, TELEGRAM_HEDEF (@grup:konu), TELEGRAM_SAHIP_ID, EIA_API_KEY.
"""

import csv
import datetime
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypedDict
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from rasathane_ortak import kagit
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi, sirayla_gonder

from . import raporlar, veri
from .cizim import (
    FIKIR,
    SAYFA_SATIRI,
    cot_ciz,
    etiket,
    gram_grafigi,
    oran_grafigi,
    oranlar_ciz,
    pano_ciz,
    sinyal_grafigi,
    sinyal_listesi_ciz,
    stok_ciz,
    takvim_ciz,
)
from .evren import EMTIALAR, TUM_SEMBOLLER
from .tarama import TURLER, Olcum, Sinyal, gram_altin, olc, oranlar, rekor_mu, sinyaller

_MIN_ORAN = 0.80  # emtiaların bu kadarında bugünün verisi yoksa gönderim yok
_LISTE_ESIGI = 4
_SUSTURMA_GUN = 10
_SUSTURULAN = {"zirve_52", "dip_52", "oran", "gram"}
_ARA = 3.2  # Telegram grup sınırı ~20 mesaj/dk
_NY = ZoneInfo("America/New_York")
_ANA = "GC=F"

log = logging.getLogger("emtia")


class Sonuc(TypedDict):
    durum: Literal["islem_yok", "eksik_veri", "zaten_gonderildi", "kart_yok", "kuru", "gonderildi"]
    kart_sayisi: int


Indirici = Callable[[list[str]], dict[str, pd.DataFrame]]
RaporKaynagi = Callable[[], dict[str, Any]]


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


def _susturulanlar(yol: Path, tarih: str, gunler: list[str]) -> set[tuple[str, str]]:
    if not yol.exists():
        return set()
    once = [g for g in gunler if g < tarih][-_SUSTURMA_GUN:]
    sinir = once[0] if once else tarih
    with open(yol, encoding="utf-8", newline="") as f:
        return {(r["tur"], r["sembol"]) for r in csv.DictReader(f) if sinir <= r["tarih"] < tarih}


def _kaydet(yol: Path, tarih: str, ciftler: list[tuple[str, str]]) -> None:
    yeni = not yol.exists()
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if yeni:
            w.writerow(["tarih", "tur", "sembol"])
        for tur, sembol in ciftler:
            w.writerow([tarih, tur, sembol])


def raporlari_al() -> dict[str, Any]:
    """EIA ve CFTC; biri düşerse ötekiler yine gelir (düşen anahtar sonuçta olmaz)."""
    out: dict[str, Any] = {}
    try:
        out["eia_petrol"] = [raporlar.eia_stok(s) for s in raporlar.PETROL]
    except Exception as e:
        log.warning("EIA petrol alınamadı: %s", e)
    try:
        out["eia_gaz"] = [raporlar.eia_stok(raporlar.DOGALGAZ)]
    except Exception as e:
        log.warning("EIA doğalgaz alınamadı: %s", e)
    pozisyonlar = []
    for kod, sembol in raporlar.COT_KODLARI:
        try:
            pozisyonlar.append(raporlar.cot(kod, sembol))
        except Exception as e:
            log.warning("CFTC %s alınamadı: %s", sembol, e)
    if pozisyonlar:
        son = max(p.donem for p in pozisyonlar)
        out["cot"] = [p for p in pozisyonlar if p.donem == son]
    return out


def _haftanin_ilki(tarih: str, gunler: list[str]) -> bool:
    d = datetime.date.fromisoformat(tarih)
    pzt = (d - datetime.timedelta(days=d.weekday())).isoformat()
    return not any(pzt <= g < tarih for g in gunler)


def calistir(
    kuru: bool,
    tarih: str | None = None,
    cikti: Path = Path("cikti"),
    simdi: datetime.datetime | None = None,
    veri_dizini: Path = Path("veri"),
    indir: Indirici = veri.indir,
    rapor_kaynagi: RaporKaynagi = raporlari_al,
) -> Sonuc:
    simdi = simdi or datetime.datetime.now(datetime.timezone.utc)
    tablolar = indir(TUM_SEMBOLLER)
    if _ANA not in tablolar:
        _sahibe("Emtia: Yahoo'dan altın vadeli verisi alınamadı, gönderim yok.")
        return {"durum": "eksik_veri", "kart_sayisi": 0}
    gunler = [g.date().isoformat() for g in tablolar[_ANA].index]
    if tarih is None:
        tarih = gunler[-1]
        if tarih != simdi.astimezone(_NY).date().isoformat():
            return {"durum": "islem_yok", "kart_sayisi": 0}
    elif tarih != gunler[-1]:
        raise ValueError(f"yalnız son seans ({gunler[-1]}) üretilebilir: {tarih}")

    durum_yolu = veri_dizini / "durum.json"
    durum = _json_oku(durum_yolu)
    if not kuru and tarih in durum.get("gunler", []):
        return {"durum": "zaten_gonderildi", "kart_sayisi": 0}

    bugunku = {s: df for s, df in tablolar.items() if df.index[-1].date().isoformat() == tarih}
    emtia_sayisi = sum(e.sembol in bugunku for e in EMTIALAR)
    if emtia_sayisi < _MIN_ORAN * len(EMTIALAR):
        _sahibe(f"Emtia {tarih}: yalnız {emtia_sayisi}/{len(EMTIALAR)} emtiada bugünün verisi var.")
        return {"durum": "eksik_veri", "kart_sayisi": 0}

    olcumler: dict[str, Olcum] = {}
    bulunan: list[Sinyal] = []
    for sembol, df in bugunku.items():
        try:
            o = olc(sembol, df)
        except Exception as e:
            log.warning("%s ölçülemedi: %s", sembol, e)
            continue
        if o is None:
            continue
        olcumler[sembol] = o
        if any(e.sembol == sembol for e in EMTIALAR):
            bulunan.extend(sinyaller(sembol, df, o))

    gram = gram_altin(tablolar)
    gram_olcum = None
    if gram is not None and gram.index[-1].date().isoformat() == tarih:
        gram_olcum = olc("gram", pd.DataFrame({"Close": gram}))

    sinyal_yolu = veri_dizini / "sinyal_kaydi.csv"
    susturulan = _susturulanlar(sinyal_yolu, tarih, gunler)
    kaydedilecek: list[tuple[str, str]] = []
    kartlar: list[tuple[str, kagit.Kart]] = []
    grafikler: list[tuple[str, kagit.Grafik, str]] = []
    gun_tarihi = kagit.tarih_metni(datetime.date.fromisoformat(tarih))

    if _haftanin_ilki(tarih, gunler):
        kartlar.append(("takvim", takvim_ciz(tarih)))
    kartlar.append(("pano", pano_ciz(olcumler, gram_olcum, tarih)))
    oran_olcumleri = oranlar(bugunku)
    if oran_olcumleri:
        kartlar.append(("oranlar", oranlar_ciz(oran_olcumleri, tarih)))

    if (
        gram is not None
        and gram_olcum is not None
        and rekor_mu(gram)
        and ("gram", "gram") not in susturulan
    ):
        grafikler.append(("grafik:gram", gram_grafigi(gram, tarih), f"#Gram_altın | {gun_tarihi}"))
        kaydedilecek.append(("gram", "gram"))

    for r in oran_olcumleri:
        if r.uc and ("oran", r.oran.anahtar) not in susturulan:
            grafikler.append(
                (
                    f"grafik:oran:{r.oran.anahtar}",
                    oran_grafigi(r, tarih),
                    f"{r.oran.ad} | {gun_tarihi}",
                )
            )
            kaydedilecek.append(("oran", r.oran.anahtar))

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
                gr = sinyal_grafigi(sy, bugunku[sy.sembol], tarih)
            except Exception as e:
                log.warning("%s grafiği çizilemedi: %s", sy.sembol, e)
                continue
            aciklama = f"{etiket(sy.sembol)} | {TURLER[tur]} | {gun_tarihi}"
            grafikler.append((f"grafik:{tur}:{sy.sembol}", gr, aciklama))
            if tur in _SUSTURULAN:
                kaydedilecek.append((tur, sy.sembol))

    son_raporlar: dict[str, str] = dict(durum.get("raporlar", {}))
    yeni_raporlar: dict[str, str] = {}
    rapor = rapor_kaynagi()
    for anahtar, ad_ in (
        ("eia_petrol", "EIA Petrol Stokları"),
        ("eia_gaz", "EIA Doğalgaz Depoları"),
    ):
        stoklar = rapor.get(anahtar)
        if stoklar and stoklar[0].donem > son_raporlar.get(anahtar, ""):
            kartlar.append((f"{anahtar}:{stoklar[0].donem}", stok_ciz(ad_, stoklar)))
            yeni_raporlar[anahtar] = stoklar[0].donem
    pozisyonlar = rapor.get("cot")
    if pozisyonlar and pozisyonlar[0].donem > son_raporlar.get("cot", ""):
        kartlar.append((f"cot:{pozisyonlar[0].donem}", cot_ciz(pozisyonlar)))
        yeni_raporlar["cot"] = pozisyonlar[0].donem

    gidenler: list[Giden] = []
    for anahtar, k in kartlar:
        for sf in kagit.ciz(k, sayfa_basina=SAYFA_SATIRI):
            gidenler.append(
                Giden(
                    anahtar,
                    sf.no,
                    sf.png,
                    kagit.mesaj_metni(FIKIR, k.ad, k.tarih, sf.no, sf.toplam),
                )
            )
    for anahtar, gr, aciklama in grafikler:
        gidenler.append(Giden(anahtar, 1, kagit.grafik_ciz(gr), aciklama))

    cikti.mkdir(parents=True, exist_ok=True)
    for i, g in enumerate(gidenler):
        (cikti / f"{tarih}_{i:03d}.png").write_bytes(g.png)
    if kuru:
        return {"durum": "kuru" if gidenler else "kart_yok", "kart_sayisi": len(gidenler)}

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
        _sahibe(f"Emtia {tarih}: gönderim başarısız (giden kartlar kaydedildi): {e}")
        raise
    _kaydet(sinyal_yolu, tarih, kaydedilecek)
    son_raporlar.update(yeni_raporlar)
    durum["raporlar"] = son_raporlar
    durum["gunler"] = sorted({*durum.get("gunler", []), tarih})[-60:]
    _json_yaz(durum_yolu, durum)
    return {"durum": "gonderildi", "kart_sayisi": len(gidenler)}
