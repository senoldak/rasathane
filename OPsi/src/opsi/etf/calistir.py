# src/opsi/etf/calistir.py
"""ETF Radarı günlük akışı: ETF listesi → toplu fiyat → sinyaller → kartlar → gönderim.

Kartlar: Yeni ETF'ler (haftanın ilk işlem günü), Yükselen Temalar (Cuma), her gün sinyal türü
başına liste (4 ve üstünde) ve her sinyal için fiyat grafiği. Aynı ETF ve tür 20 işlem günü
içinde tekrarlanmaz.

Ayarlar ortamdan: TELEGRAM_BOT_TOKEN, TELEGRAM_HEDEF (@grup:konu), TELEGRAM_SAHIP_ID.
"""

import csv
import datetime
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypedDict

import pandas as pd
from rasathane_ortak import kagit
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi, sirayla_gonder

from ..kanal.calistir import _spy_gunleri, haftanin_ilki, islem_gunu
from ..kanal.cizim import FIKIR, SAYFA_SATIRI
from ..kanal.gecmis import gonderildi_isaretle, gonderildi_mi
from ..kanal.telegram import requests_istek, sahibe_yaz
from . import liste as etf_liste
from . import veri as etf_veri
from .cizim import etiket, sinyal_grafigi, sinyal_listesi_ciz, temalar_ciz, yeni_ciz
from .tarama import TURLER, Olcum, Sinyal, kopyalari_ayikla, olc, sinyaller

_MIN_ORAN = 0.80  # listedeki ETF'lerin bu kadarının verisi gelmezse gönderim yok
_TEMA_SATIRI = 20
_LISTE_ESIGI = 4  # bir türde bu kadar ve üstü sinyal varsa önce liste kartı
_SUSTURMA_GUN = 20
_ARA = 3.2  # Telegram grup sınırı ~20 mesaj/dk

log = logging.getLogger("opsi.etf")


class Sonuc(TypedDict):
    durum: Literal[
        "islem_yok", "spy_yok", "zaten_gonderildi", "eksik_veri", "kart_yok", "kuru", "gonderildi"
    ]
    kart_sayisi: int
    sinyal_sayisi: int


Indirici = Callable[[list[str]], dict[str, pd.DataFrame]]
ListeKaynagi = Callable[[], dict[str, etf_liste.Guncel]]


def _sahibe(metin: str) -> None:
    token, sahip = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_SAHIP_ID")
    if token and sahip:
        sahibe_yaz(token, sahip, metin)
    else:
        log.error("sahibe yazılamadı (token/sahip yok): %s", metin)


def _susturulanlar(yol: Path, tarih: str, gunler: list[str]) -> set[tuple[str, str]]:
    """Son 20 işlem gününde (bugün hariç) gönderilmiş (tür, sembol) çiftleri."""
    if not yol.exists():
        return set()
    once = [g for g in gunler if g < tarih][-_SUSTURMA_GUN:]
    sinir = once[0] if once else tarih
    with open(yol, encoding="utf-8", newline="") as f:
        return {(r["tur"], r["sembol"]) for r in csv.DictReader(f) if sinir <= r["tarih"] < tarih}


def _kaydet(yol: Path, tarih: str, sinyaller_: list[Sinyal]) -> None:
    yeni = not yol.exists()
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if yeni:
            w.writerow(["tarih", "tur", "sembol"])
        for s in sinyaller_:
            w.writerow([tarih, s.tur, s.sembol])


def _yeni_baslangici(tarih: str, gunler: list[str]) -> str:
    """Bir önceki haftanın ilk işlem günü: o günden (dahil) bugüne (hariç) girenler kartta."""
    d = datetime.date.fromisoformat(tarih)
    gecen_pzt = (d - datetime.timedelta(days=d.weekday() + 7)).isoformat()
    return next((g for g in gunler if gecen_pzt <= g), gecen_pzt)


def calistir(
    kuru: bool,
    tarih: str | None = None,
    cikti: Path = Path("cikti/etf"),
    simdi: datetime.datetime | None = None,
    veri: Path = Path("kanal_veri/etf"),
    indir: Indirici = etf_veri.indir,
    liste_kaynagi: ListeKaynagi = etf_liste.nasdaq_listesi,
) -> Sonuc:
    simdi = simdi or datetime.datetime.now(datetime.UTC)
    gunler = _spy_gunleri()
    if not gunler:
        _sahibe("OPsi ETF: Yahoo'dan SPY verisi alınamadı, gönderim yok.")
        return {"durum": "spy_yok", "kart_sayisi": 0, "sinyal_sayisi": 0}
    if tarih is None:
        tarih = islem_gunu(simdi, gunler)
        if tarih is None:
            return {"durum": "islem_yok", "kart_sayisi": 0, "sinyal_sayisi": 0}
    elif tarih != gunler[-1]:
        raise ValueError(f"yalnız son seans ({gunler[-1]}) üretilebilir: {tarih}")
    gonderilen_yolu = veri / "gonderilenler.json"
    if not kuru and gonderildi_mi(tarih, gonderilen_yolu):
        return {"durum": "zaten_gonderildi", "kart_sayisi": 0, "sinyal_sayisi": 0}

    liste_yolu = veri / "etf_listesi.csv"
    try:
        guncel = liste_kaynagi()
    except Exception as e:
        _sahibe(f"OPsi ETF {tarih}: Nasdaq ETF listesi alınamadı: {e}")
        return {"durum": "eksik_veri", "kart_sayisi": 0, "sinyal_sayisi": 0}
    kayit = etf_liste.birlestir(etf_liste.oku(liste_yolu), guncel, tarih)

    tablolar = indir(sorted(set(guncel) | {"SPY"}))
    tablolar = {s: df for s, df in tablolar.items() if df.index[-1].date().isoformat() == tarih}
    oran = len(tablolar) / len(guncel) if guncel else 0.0
    if oran < _MIN_ORAN:
        _sahibe(f"OPsi ETF {tarih}: ETF'lerin yalnız %{oran * 100:.0f}'inde bugünün verisi var.")
        return {"durum": "eksik_veri", "kart_sayisi": 0, "sinyal_sayisi": 0}

    olcumler: dict[str, Olcum] = {}
    bulunan: list[Sinyal] = []
    for sembol, df in tablolar.items():
        try:
            o = olc(sembol, df)
            if o is None:
                continue
            olcumler[sembol] = o
            if sembol in guncel:
                bulunan.extend(sinyaller(sembol, df, o))
        except Exception as e:
            log.warning("%s ölçülemedi: %s", sembol, e)

    kartlar: list[tuple[str, kagit.Kart]] = []
    gun_tarihi = kagit.tarih_metni(datetime.date.fromisoformat(tarih))

    if haftanin_ilki(tarih, gunler):
        bas = _yeni_baslangici(tarih, gunler)
        yeniler = sorted(
            (e for e in kayit.values() if e["ilk_gorulme"] and bas <= e["ilk_gorulme"] < tarih),
            key=lambda e: (e["ilk_gorulme"], e["sembol"]),
        )
        if yeniler:
            kartlar.append(("yeni", yeni_ciz(yeniler, guncel, tarih, bas)))

    if datetime.date.fromisoformat(tarih).weekday() == 4:
        duz = sorted(
            (
                o
                for s, o in olcumler.items()
                if s in guncel and o.g3a is not None and not kayit[s]["kaldirac"]
            ),
            key=lambda o: -(o.g3a or 0.0),
        )
        secilen = kopyalari_ayikla([o.sembol for o in duz[: _TEMA_SATIRI * 4]], tablolar)[
            :_TEMA_SATIRI
        ]
        if secilen:
            adlar = {s: kayit[s]["ad"] for s in secilen}
            kartlar.append(
                (
                    "temalar",
                    temalar_ciz(
                        [olcumler[s] for s in secilen], adlar, olcumler.get("SPY"), tarih, len(duz)
                    ),
                )
            )

    susturulan = _susturulanlar(veri / "sinyal_kaydi.csv", tarih, gunler)
    giden_sinyaller: list[Sinyal] = []
    grafikler: list[tuple[Sinyal, kagit.Grafik]] = []
    for tur in TURLER:
        adaylar = sorted(
            (s for s in bulunan if s.tur == tur and (tur, s.sembol) not in susturulan),
            key=lambda s: -s.dolar_hacim,
        )
        kalan = set(kopyalari_ayikla([s.sembol for s in adaylar], tablolar))
        turunkiler = [s for s in adaylar if s.sembol in kalan]
        if not turunkiler:
            continue
        if len(turunkiler) >= _LISTE_ESIGI:
            kartlar.append((f"liste:{tur}", sinyal_listesi_ciz(tur, turunkiler, kayit, tarih)))
        for sy in turunkiler:
            try:
                kayit_e = kayit[sy.sembol]
                grafikler.append(
                    (
                        sy,
                        sinyal_grafigi(
                            sy, kayit_e["ad"], kayit_e["kaldirac"], tablolar[sy.sembol], tarih
                        ),
                    )
                )
                giden_sinyaller.append(sy)
            except Exception as ex:
                log.warning("%s grafiği çizilemedi: %s", sy.sembol, ex)

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
    for sy, gr in grafikler:
        aciklama = f"{etiket(sy.sembol)} | {TURLER[sy.tur]} | {gun_tarihi}"
        gidenler.append(Giden(f"grafik:{sy.tur}:{sy.sembol}", 1, kagit.grafik_ciz(gr), aciklama))

    cikti.mkdir(parents=True, exist_ok=True)
    for i, g in enumerate(gidenler):
        (cikti / f"{tarih}_{i:03d}.png").write_bytes(g.png)
    if kuru:
        durum: Literal["kuru", "kart_yok"] = "kuru" if gidenler else "kart_yok"
        return {"durum": durum, "kart_sayisi": len(gidenler), "sinyal_sayisi": len(giden_sinyaller)}

    if gidenler:
        try:
            sirayla_gonder(
                requests_istek,
                os.environ["TELEGRAM_BOT_TOKEN"],
                os.environ["TELEGRAM_HEDEF"],
                tarih,
                gidenler,
                GonderimKaydi(veri / "gonderilen_kartlar.csv"),
                ara=_ARA,
            )
        except Exception as e:
            _sahibe(f"OPsi ETF {tarih}: gönderim başarısız (giden kartlar kaydedildi): {e}")
            raise
    etf_liste.yaz(kayit, liste_yolu)
    _kaydet(veri / "sinyal_kaydi.csv", tarih, giden_sinyaller)
    gonderildi_isaretle(tarih, gonderilen_yolu)
    durum2: Literal["gonderildi", "kart_yok"] = "gonderildi" if gidenler else "kart_yok"
    return {"durum": durum2, "kart_sayisi": len(gidenler), "sinyal_sayisi": len(giden_sinyaller)}
