# src/opsi/etf/calistir.py
"""ETF Radarı günlük akışı: ETF listesi → toplu fiyat → sinyaller → kartlar → gönderim.

Her gün: Piyasa Rejimi, Olağandışı Opsiyon Hareketi, sinyal türü başına liste (4 ve üstünde)
ve her sinyal için fiyat grafiği. Haftanın ilk işlem günü: Yeni ETF'ler, Yeni ETF'lerin Seyri.
Cuma: Yükselen Temalar, en güçlü 5 temanın hisseleri, Tema Haritası, Fon Akışı.
Aynı ETF ve tür 20 işlem günü içinde tekrarlanmaz.

Ayarlar ortamdan: TELEGRAM_BOT_TOKEN, TELEGRAM_HEDEF (@grup:konu), TELEGRAM_SAHIP_ID.
"""

import csv
import datetime
import logging
import os
import re
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
from . import ag
from . import liste as etf_liste
from . import veri as etf_veri
from .cizim import (
    Hisse,
    akis_ciz,
    etiket,
    hisseler_ciz,
    opsiyon_ciz,
    rejim_ciz,
    sinyal_grafigi,
    sinyal_listesi_ciz,
    tema_haritasi_ciz,
    temalar_ciz,
    yeni_ciz,
    yeni_seyir_ciz,
)
from .ekler import (
    OPSIYON_EN_AZ_DOLAR,
    OpsiyonSatiri,
    fon_akisi,
    opsiyon_ozeti,
    rejim,
    tema_haritasi,
    yeni_seyir,
)
from .tarama import DONEM, TURLER, Olcum, Sinyal, kopyalari_ayikla, olc, sinyaller

_MIN_ORAN = 0.80  # listedeki ETF'lerin bu kadarının verisi gelmezse gönderim yok
_TEMA_SATIRI = 20
_LISTE_ESIGI = 4  # bir türde bu kadar ve üstü sinyal varsa önce liste kartı
_SUSTURMA_GUN = 20
_ARA = 3.2  # Telegram grup sınırı ~20 mesaj/dk
_HISSE_TEMA = 5  # Cuma: hisseleri gösterilen tema sayısı
_AKIS_SATIRI = 10
_VARLIK_EN_AZ_DOLAR = 20_000_000.0
_NAKIT = re.compile(r"money market|treasury|t-bill|cash|gov&agcy|government", re.IGNORECASE)

log = logging.getLogger("opsi.etf")


class Sonuc(TypedDict):
    durum: Literal[
        "islem_yok", "spy_yok", "zaten_gonderildi", "eksik_veri", "kart_yok", "kuru", "gonderildi"
    ]
    kart_sayisi: int
    sinyal_sayisi: int


Indirici = Callable[[list[str]], dict[str, pd.DataFrame]]
ListeKaynagi = Callable[[], dict[str, etf_liste.Guncel]]
ZincirKaynagi = Callable[[list[str], datetime.date], dict[str, pd.DataFrame]]
HisseKaynagi = Callable[[str], list[tuple[str, str, float]]]
VarlikKaynagi = Callable[[list[str]], dict[str, float]]


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


def _varlik_oku(yol: Path) -> pd.DataFrame:
    if not yol.exists():
        return pd.DataFrame(columns=["tarih", "sembol", "varlik"])
    return pd.read_csv(yol, dtype={"tarih": str, "sembol": str, "varlik": float})


def _varlik_yaz(yol: Path, tarih: str, bugun: dict[str, float]) -> None:
    eski = _varlik_oku(yol)
    eski = eski[eski["tarih"] != tarih]
    yeni = pd.DataFrame({"tarih": tarih, "sembol": list(bugun), "varlik": list(bugun.values())})
    yol.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([eski, yeni]).sort_values(["tarih", "sembol"]).to_csv(
        yol, index=False, lineterminator="\n", float_format="%.0f"
    )


def _zirvede(df: pd.DataFrame) -> bool:
    c = df["Close"].to_numpy(dtype=float)
    return len(c) > DONEM and c[-1] >= c[-1 - DONEM :].max()


def calistir(
    kuru: bool,
    tarih: str | None = None,
    cikti: Path = Path("cikti/etf"),
    simdi: datetime.datetime | None = None,
    veri: Path = Path("kanal_veri/etf"),
    indir: Indirici = etf_veri.indir,
    liste_kaynagi: ListeKaynagi = etf_liste.nasdaq_listesi,
    zincir_kaynagi: ZincirKaynagi = ag.zincirler,
    hisse_kaynagi: HisseKaynagi = ag.ilk_hisseler,
    varlik_kaynagi: VarlikKaynagi = ag.varliklar,
    hepsi: bool = False,
) -> Sonuc:
    """hepsi: haftalık kartları da (Pazartesi ve Cuma) bugün üret; önizleme için."""
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
    spy = tablolar["SPY"]["Close"] if "SPY" in tablolar else None
    for sembol, df in tablolar.items():
        try:
            o = olc(sembol, df)
            if o is None:
                continue
            olcumler[sembol] = o
            if sembol in guncel:
                bulunan.extend(sinyaller(sembol, df, o, spy))
        except Exception as e:
            log.warning("%s ölçülemedi: %s", sembol, e)

    kartlar: list[tuple[str, kagit.Kart]] = []
    gun_tarihi = kagit.tarih_metni(datetime.date.fromisoformat(tarih))
    cuma = hepsi or datetime.date.fromisoformat(tarih).weekday() == 4
    adlar = {s: e["ad"] for s, e in kayit.items()}

    rejim_satirlari = rejim(tablolar)
    if rejim_satirlari:
        kartlar.append(("rejim", rejim_ciz(rejim_satirlari, tarih)))

    opsiyonlu = sorted(
        (s for s, o in olcumler.items() if s in guncel and o.dolar_hacim >= OPSIYON_EN_AZ_DOLAR),
        key=lambda s: -olcumler[s].dolar_hacim,
    )
    opsiyon_satirlari: list[OpsiyonSatiri] = []
    for s, z in zincir_kaynagi(opsiyonlu, datetime.date.fromisoformat(tarih)).items():
        try:
            opsiyon_satirlari.extend(opsiyon_ozeti(s, z))
        except Exception as e:
            log.warning("%s opsiyon özeti çıkarılamadı: %s", s, e)
    if opsiyon_satirlari:
        opsiyon_satirlari.sort(key=lambda r: -r.oran)
        kartlar.append(("opsiyon", opsiyon_ciz(opsiyon_satirlari, adlar, tarih, len(opsiyonlu))))

    varlikli = [
        s
        for s, o in olcumler.items()
        if s in guncel and o.dolar_hacim >= _VARLIK_EN_AZ_DOLAR and not kayit[s]["kaldirac"]
    ]
    bugun_varlik = varlik_kaynagi(varlikli) if varlikli else {}
    varlik_yolu = veri / "varliklar.csv"

    if hepsi or haftanin_ilki(tarih, gunler):
        bas = _yeni_baslangici(tarih, gunler)
        yeniler = sorted(
            (e for e in kayit.values() if e["ilk_gorulme"] and bas <= e["ilk_gorulme"] < tarih),
            key=lambda e: (e["ilk_gorulme"], e["sembol"]),
        )
        if yeniler:
            kartlar.append(("yeni", yeni_ciz(yeniler, guncel, tarih, bas)))
        seyir = yeni_seyir(kayit, tablolar, tarih, bas)
        if seyir:
            kartlar.append(("seyir", yeni_seyir_ciz(seyir, tarih)))

    if cuma:
        duz = sorted(
            (
                o
                for s, o in olcumler.items()
                if s in guncel and o.g3a is not None and not etf_liste.tema_disi_mi(kayit[s])
            ),
            key=lambda o: -(o.g3a or 0.0),
        )
        secilen = kopyalari_ayikla([o.sembol for o in duz[: _TEMA_SATIRI * 4]], tablolar)[
            :_TEMA_SATIRI
        ]
        if secilen:
            kartlar.append(
                (
                    "temalar",
                    temalar_ciz(
                        [olcumler[s] for s in secilen], adlar, olcumler.get("SPY"), tarih, len(duz)
                    ),
                )
            )
        for s in secilen[:_HISSE_TEMA]:
            try:
                # Vadeli işlemle çalışan fonlar (BWET gibi) hisse yerine nakit fonu tutar.
                ilk = [
                    h
                    for h in hisse_kaynagi(s)
                    if not h[0].endswith("XX") and not _NAKIT.search(h[1])
                ]
                if len(ilk) < 3:
                    continue
                h_tablolar = indir([h for h, _, _ in ilk])
                hisseler: list[Hisse] = [
                    (
                        h,
                        ad,
                        agirlik,
                        olc(h, h_tablolar[h]) if h in h_tablolar else None,
                        h in h_tablolar and _zirvede(h_tablolar[h]),
                    )
                    for h, ad, agirlik in ilk
                ]
                kartlar.append((f"hisseler:{s}", hisseler_ciz(s, kayit[s]["ad"], hisseler, tarih)))
            except Exception as e:
                log.warning("%s hisse kartı atlandı: %s", s, e)

        harita = tema_haritasi({s: o for s, o in olcumler.items() if s in guncel}, kayit)
        if harita:
            kartlar.append(("harita", tema_haritasi_ciz(harita, tarih)))

        gecmis_varlik = _varlik_oku(varlik_yolu)
        gecmis_varlik = gecmis_varlik[gecmis_varlik["tarih"] != tarih]
        bugunku = pd.DataFrame(
            {"tarih": tarih, "sembol": list(bugun_varlik), "varlik": list(bugun_varlik.values())}
        )
        akis = fon_akisi(pd.concat([gecmis_varlik, bugunku]), tablolar, adlar, tarih)
        girenler = sorted((a for a in akis if a.akis > 0), key=lambda a: -a.akis)[:_AKIS_SATIRI]
        cikanlar = sorted((a for a in akis if a.akis < 0), key=lambda a: a.akis)[:_AKIS_SATIRI]
        if girenler or cikanlar:
            kartlar.append(("akis", akis_ciz(girenler, cikanlar, tarih)))

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
    if bugun_varlik:
        _varlik_yaz(varlik_yolu, tarih, bugun_varlik)
    _kaydet(veri / "sinyal_kaydi.csv", tarih, giden_sinyaller)
    gonderildi_isaretle(tarih, gonderilen_yolu)
    durum2: Literal["gonderildi", "kart_yok"] = "gonderildi" if gidenler else "kart_yok"
    return {"durum": durum2, "kart_sayisi": len(gidenler), "sinyal_sayisi": len(giden_sinyaller)}
