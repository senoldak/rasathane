# src/opsi/site_aktar.py
"""Rasathane sitesi için OPsi verisi: `site-veri/opsi/` altında sayfa ve seri JSON'ları.

Kanal (opsiyon taraması, IV durumu, IV sarsıntısı, aşağı yön primi) ve ETF Radarı (rejim,
opsiyon, hareketler, yeni ETF'ler, tema haritası, temalar, fon akışı) aynı bölümde durur.
Sayfalar her koşuda o günün durumundan yeniden yazılır. Geçmiş serileri kanal geçmişinden
(kanal_veri/iv_gecmisi.csv) ve ETF hareket kaydından (kanal_veri/etf/sinyal_kaydi.csv) okunur.
"""

from __future__ import annotations

import csv
import datetime
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz, seri_yaz

from .etf import ekler
from .etf import liste as etf_liste
from .etf import tarama as etf_tarama
from .etf.ekler import AkisSatiri, OpsiyonSatiri, RejimSatiri
from .kanal import gecmis as kanal_gecmis
from .kanal.gecmis import Kayit
from .kanal.kartlar import asagi_yon_primi, csp_kartlari, iv_sarsintisi
from .kanal.olcum import CspAday

BOLUM = "opsi"
GECMIS_GUN = 60  # sarsıntı ve hareket sayfalarında geriye dönük işlem günü
SERI_GUN = 252  # ETF fiyat serisi: son bir yıl
BILANCO_YAKIN = 7  # bilanço bu kadar iş günü içindeyse "Yakın"
EN_AZ_GECMIS = 20  # bundan kısa IV geçmişinde konum yüzdeliği yazılmaz
TEMA_SATIRI = 20
TEMA_ADAY = 4 * TEMA_SATIRI
AKIS_SATIRI = 10
YENI_GUN = 45

_YAHOO = Kaynak("Yahoo Finance", "https://finance.yahoo.com/")
_NASDAQ = Kaynak("Nasdaq ETF listesi", "https://www.nasdaq.com/market-activity/etf")

log = logging.getLogger("opsi.site")

Noktalar = Mapping[str, list[tuple[datetime.date, float]]]


def _sayfa(kok: Path, sayfa: str, **k: Any) -> Path:
    return Path(sayfa_yaz(kok, BOLUM, sayfa, **k))


def _anahtar(on: str, sembol: str, yazilan: set[str]) -> str | None:
    """Satırın grafik serisi: yalnız o sembolün seri dosyası yazıldıysa."""
    return f"{on}-{sembol}" if sembol in yazilan else None


def _seriler(
    kok: Path,
    on: str,
    noktalar: Noktalar,
    adlar: Mapping[str, str],
    birim: str,
    etiket: str,
    isaretler: Mapping[str, list[tuple[datetime.date, str]]] | None = None,
) -> set[str]:
    """`on-SEMBOL` seri dosyalarını yazar; geçersiz bir sembol yalnız kendini atlar."""
    yazilan: set[str] = set()
    for sembol, nokta in noktalar.items():
        if not nokta:
            continue
        try:
            seri_yaz(
                kok,
                BOLUM,
                f"{on}-{sembol}",
                nokta,
                ad=f"{adlar.get(sembol, sembol)} · {etiket}",
                birim=birim,
                isaretler=(isaretler or {}).get(sembol, []),
            )
            yazilan.add(sembol)
        except ValueError as e:
            log.warning("seri atlandı (%s): %s", sembol, e)
    return yazilan


def _yakin(bilanco_gun: int | None) -> bool:
    return bilanco_gun is not None and 0 <= bilanco_gun <= BILANCO_YAKIN


def kanal_aktar(
    kok: Path,
    simdi: datetime.datetime,
    gecmis: Sequence[Kayit],
    bugun: Sequence[Kayit],
    adaylar: Sequence[CspAday],
    adlar: Mapping[str, str],
) -> list[Path]:
    """Kanal sayfaları ve fiyat/IV serileri. `gecmis` bugünü içermez; `bugun` yalnız bugünü."""
    tum = sorted([*gecmis, *bugun], key=lambda k: (k["tarih"], k["sembol"]))
    fiyat: dict[str, list[tuple[datetime.date, float]]] = defaultdict(list)
    iv: dict[str, list[tuple[datetime.date, float]]] = defaultdict(list)
    ilk: dict[str, str] = {}
    iv_ham: dict[str, list[float]] = defaultdict(list)  # tarih sırasıyla, bugüne kadar
    for k in tum:
        g = datetime.date.fromisoformat(k["tarih"])
        fiyat[k["sembol"]].append((g, k["kapanis"]))
        if k["iv30"] is not None:
            iv[k["sembol"]].append((g, 100.0 * k["iv30"]))
            iv_ham[k["sembol"]].append(k["iv30"])
            ilk.setdefault(k["sembol"], k["tarih"])
    fiyat_var = _seriler(kok, "fiyat", fiyat, adlar, "$", "kapanış")
    iv_var = _seriler(kok, "iv", iv, adlar, "%", "IV30")
    return [
        _opsiyon_taramasi(kok, simdi, gecmis, bugun, adaylar, adlar, fiyat_var),
        _iv_durumu(kok, simdi, iv_ham, bugun, adlar, ilk, iv_var),
        _iv_sarsintisi(kok, simdi, tum, adlar, iv_var),
        _asagi_yon_primi(kok, simdi, bugun, adlar, iv_var),
    ]


def _opsiyon_taramasi(
    kok: Path,
    simdi: datetime.datetime,
    gecmis: Sequence[Kayit],
    bugun: Sequence[Kayit],
    adaylar: Sequence[CspAday],
    adlar: Mapping[str, str],
    fiyat_var: set[str],
) -> Path:
    satirlar: list[dict[str, object]] = []
    for kart in csp_kartlari(list(adaylar), list(bugun), list(gecmis), dict(adlar)):
        for r in kart["satirlar"]:
            s = r["sembol"]
            satirlar.append(
                {
                    "bant": kart["bant"],
                    "sembol": s,
                    "ad": r["ad"],
                    "fiyat": r["fiyat"],
                    "hareket": r["hareket_yuzde"],
                    "iv30": r["iv30"],
                    "konum": r["iv_konum"],
                    "skor": r["skor"],
                    "seri": _anahtar("fiyat", s, fiyat_var),
                }
            )
    return _sayfa(
        kok,
        "opsiyon-taramasi",
        baslik="Opsiyon taraması",
        aciklama="Sermaye bandına göre nakit teminatlı put adayları. Beklenen hareket, 30 günlük "
        "IV'den bir standart sapma olarak hesaplanır.",
        guncellendi=simdi,
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("bant", "Sermaye bandı", "metin"),
            Sutun("sembol", "Sembol", "metin"),
            Sutun("ad", "Ad", "metin"),
            Sutun("fiyat", "Fiyat", "sayi", 2),
            Sutun("hareket", "Beklenen hareket", "yuzde", 1),
            Sutun("iv30", "IV30", "yuzde", 1),
            Sutun("konum", "IV konumu", "yuzde", 0),
            Sutun("skor", "Skor", "sayi", 1),
        ],
        satirlar=satirlar,
        suzgecler=["bant"],
    )


def _iv_durumu(
    kok: Path,
    simdi: datetime.datetime,
    iv_ham: Mapping[str, list[float]],
    bugun: Sequence[Kayit],
    adlar: Mapping[str, str],
    ilk: Mapping[str, str],
    iv_var: set[str],
) -> Path:
    satirlar: list[dict[str, object]] = []
    for k in sorted(bugun, key=lambda k: k["sembol"]):
        s = k["sembol"]
        seri = iv_ham.get(s, [])
        konum: float | None = None
        if len(seri) >= EN_AZ_GECMIS:
            konum, _ = kanal_gecmis.iv_konum(seri, ilk.get(s, k["tarih"]))
        satirlar.append(
            {
                "sembol": s,
                "ad": adlar.get(s, s),
                "kapanis": k["kapanis"],
                "iv30": k["iv30"],
                "atm": k["atm_iv"],
                "skew": k["skew25"],
                "konum": konum,
                "bilanco": "Yakın" if _yakin(k["bilanco_gun"]) else "Diğer",
                "bilanco_gun": k["bilanco_gun"],
                "seri": _anahtar("iv", s, iv_var),
            }
        )
    return _sayfa(
        kok,
        "iv-durumu",
        baslik="IV durumu",
        aciklama="Evrendeki hisse ve ETF'lerin 30 günlük örtük oynaklığı, ATM IV ve 25 delta put "
        "skew'u. IV konumu, son bir yıldaki yerini gösterir.",
        guncellendi=simdi,
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("sembol", "Sembol", "metin"),
            Sutun("ad", "Ad", "metin"),
            Sutun("kapanis", "Kapanış", "sayi", 2),
            Sutun("iv30", "IV30", "yuzde", 1),
            Sutun("atm", "ATM IV", "yuzde", 1),
            Sutun("skew", "Put skew (25Δ/ATM)", "sayi", 3),
            Sutun("konum", "IV konumu", "yuzde", 0),
            Sutun("bilanco", "Bilanço", "metin"),
            Sutun("bilanco_gun", "Bilançoya gün", "sayi", 0),
        ],
        satirlar=satirlar,
        suzgecler=["bilanco"],
    )


def _iv_sarsintisi(
    kok: Path,
    simdi: datetime.datetime,
    tum: Sequence[Kayit],
    adlar: Mapping[str, str],
    iv_var: set[str],
) -> Path:
    gunler = sorted({k["tarih"] for k in tum})
    gun: dict[str, list[Kayit]] = defaultdict(list)
    for k in tum:
        gun[k["tarih"]].append(k)
    satirlar: list[dict[str, object]] = []
    for i in range(max(1, len(gunler) - GECMIS_GUN), len(gunler)):
        d, once = gunler[i], gunler[i - 1]
        bosluk = int(np.busday_count(once, d))
        for r in iv_sarsintisi(gun[d], gun[once], dict(adlar), bosluk) or []:
            satirlar.append(
                {
                    "tarih": d,
                    "sembol": r["sembol"],
                    "ad": r["ad"],
                    "kapanis": r["kapanis"],
                    "fiyat": r["fiyat_degisim"],
                    "iv_once": r["iv_once"],
                    "iv_simdi": r["iv_simdi"],
                    "iv_degisim": r["iv_degisim"],
                    "bilanco": "Yakın" if r["bilanco"] else "Diğer",
                    "seri": _anahtar("iv", r["sembol"], iv_var),
                }
            )
    satirlar.reverse()  # en yeni gün üstte
    return _sayfa(
        kok,
        "iv-sarsintisi",
        baslik="IV sarsıntısı",
        aciklama="Son 60 işlem gününde IV30'u en çok düşen ve en çok yükselen dörder hisse "
        "ve ETF. Bilanço yakınlığı ayrı sütunda gösterilir.",
        guncellendi=simdi,
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("tarih", "Tarih", "tarih"),
            Sutun("sembol", "Sembol", "metin"),
            Sutun("ad", "Ad", "metin"),
            Sutun("kapanis", "Kapanış", "sayi", 2),
            Sutun("fiyat", "Fiyat değişimi", "yuzde", 1),
            Sutun("iv_once", "IV30 önce", "yuzde", 1),
            Sutun("iv_simdi", "IV30 şimdi", "yuzde", 1),
            Sutun("iv_degisim", "IV30 değişimi", "yuzde", 1),
            Sutun("bilanco", "Bilanço", "metin"),
        ],
        satirlar=satirlar,
        suzgecler=["bilanco"],
    )


def _asagi_yon_primi(
    kok: Path,
    simdi: datetime.datetime,
    bugun: Sequence[Kayit],
    adlar: Mapping[str, str],
    iv_var: set[str],
) -> Path:
    pk = asagi_yon_primi(list(bugun), dict(adlar))
    satirlar: list[dict[str, object]] = []
    for r in pk["satirlar"] if pk else []:
        satirlar.append(
            {
                "sembol": r["sembol"],
                "ad": r["ad"],
                "kapanis": r["kapanis"],
                "skew": r["skew"],
                "fark": r["fark"],
                "seri": _anahtar("iv", r["sembol"], iv_var),
            }
        )
    return _sayfa(
        kok,
        "asagi-yon-primi",
        baslik="Aşağı yön primi",
        aciklama="Evrendeki 25 delta put'un ATM IV'ye oranı en yüksek altı hisse. Fark, evren "
        "ortancasından ne kadar yukarıda olduklarını gösterir.",
        guncellendi=simdi,
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("sembol", "Sembol", "metin"),
            Sutun("ad", "Ad", "metin"),
            Sutun("kapanis", "Kapanış", "sayi", 2),
            Sutun("skew", "Put skew (25Δ/ATM)", "sayi", 3),
            Sutun("fark", "Ortancadan fark", "sayi", 3),
        ],
        satirlar=satirlar,
    )


# ---------------------------------------------------------------- ETF Radarı


def etf_aktar(
    kok: Path,
    simdi: datetime.datetime,
    tarih: str,
    tablolar: Mapping[str, pd.DataFrame],
    olcumler: Mapping[str, etf_tarama.Olcum],
    kayit: Mapping[str, etf_liste.Etf],
    adlar: Mapping[str, str],
    rejim_satirlari: Sequence[RejimSatiri],
    opsiyon_satirlari: Sequence[OpsiyonSatiri],
    akis: Sequence[AkisSatiri],
    bugun_hareketler: Sequence[etf_tarama.Sinyal],
    hareket_kaydi: Path,
) -> list[Path]:
    """ETF Radarı sayfaları ve ETF fiyat serileri. `olcumler` yalnız listedeki ETF'leri içerir."""
    hareketler = _hareketler(hareket_kaydi, tarih, bugun_hareketler)
    isaretler: dict[str, list[tuple[datetime.date, str]]] = defaultdict(list)
    for gun, tur, sembol in hareketler:
        isaretler[sembol].append(
            (datetime.date.fromisoformat(gun), etf_tarama.TURLER.get(tur, tur))
        )
    temalar = _temalar(olcumler, kayit, tablolar)
    semboller = {s for _, _, s in hareketler} | {o.sembol for o in temalar}
    noktalar = {s: _etf_noktalari(tablolar[s]) for s in semboller if s in tablolar}
    yazilan = _seriler(kok, "etf", noktalar, adlar, "$", "kapanış", isaretler)
    return [
        _etf_sayfa(
            kok,
            "etf-rejim",
            simdi,
            "Piyasa rejimi",
            "Seçilmiş ETF çiftlerinin oranı ve 50 günlük ortalamasının üstünde olup olmadığı.",
            [
                Sutun("ad", "Oran", "metin"),
                Sutun("pay", "Pay", "metin"),
                Sutun("payda", "Payda", "metin"),
                Sutun("anlam", "Yükselirse", "metin"),
                Sutun("oran", "Oran değeri", "sayi", 3),
                Sutun("g1a", "1 ay değişim", "yuzde", 1),
                Sutun("sma50", "50 günlük ortalama", "metin"),
            ],
            [
                {
                    "ad": r.ad,
                    "pay": r.pay,
                    "payda": r.payda,
                    "anlam": r.anlam,
                    "oran": r.oran,
                    "g1a": r.g1a,
                    "sma50": "Üstünde" if r.sma50_ustu else "Altında",
                }
                for r in rejim_satirlari
            ],
        ),
        _etf_sayfa(
            kok,
            "etf-opsiyon",
            simdi,
            "Olağandışı opsiyon hareketi",
            "Günlük opsiyon hacminin açık pozisyona oranı yüksek hisse ve ETF'ler.",
            [
                Sutun("sembol", "Sembol", "metin"),
                Sutun("ad", "Ad", "metin"),
                Sutun("yon", "Yön", "metin"),
                Sutun("hacim", "Hacim", "sayi", 0),
                Sutun("acik", "Açık pozisyon", "sayi", 0),
                Sutun("oran", "Hacim / açık", "sayi", 2),
                Sutun("put_cagri", "Put / çağrı", "sayi", 2),
                Sutun("en_aktif", "En aktif", "metin"),
            ],
            [
                {
                    "sembol": r.sembol,
                    "ad": adlar.get(r.sembol, r.sembol),
                    "yon": r.yon,
                    "hacim": r.hacim,
                    "acik": r.acik,
                    "oran": r.oran,
                    "put_cagri": r.put_cagri,
                    "en_aktif": r.en_aktif,
                }
                for r in opsiyon_satirlari
            ],
            suzgecler=["yon"],
        ),
        _etf_sayfa(
            kok,
            "etf-hareketler",
            simdi,
            "ETF hareketleri",
            "Son 60 işlem gününde 52 hafta zirvesine çıkan, SMA 200'ü kesen, hacmi patlayan "
            "ve SPY'ye göre güçlenen ETF'ler.",
            [
                Sutun("tarih", "Tarih", "tarih"),
                Sutun("tur", "Hareket", "metin"),
                Sutun("ad", "Ad", "metin"),
                Sutun("sembol", "Sembol", "metin"),
            ],
            [
                {
                    "tarih": gun,
                    "tur": etf_tarama.TURLER.get(tur, tur),
                    "ad": adlar.get(sembol, sembol),
                    "sembol": sembol,
                    "seri": _anahtar("etf", sembol, yazilan),
                }
                for gun, tur, sembol in sorted(hareketler, reverse=True)
            ],
            suzgecler=["tur"],
        ),
        _etf_sayfa(
            kok,
            "etf-yeni",
            simdi,
            "Yeni ETF'ler",
            "Son 45 günde listeye giren ETF'ler; ilk günden bu yana getiri ve işlem tutarı değişimi.",
            [
                Sutun("ilk_gorulme", "Listeye giriş", "tarih"),
                Sutun("sembol", "Sembol", "metin"),
                Sutun("ad", "Ad", "metin"),
                Sutun("getiri", "Girişten bu yana", "yuzde", 1),
                Sutun("ilk_hacim", "İlk 5 gün ort. tutar ($)", "sayi", 0),
                Sutun("son_hacim", "Son 5 gün ort. tutar ($)", "sayi", 0),
            ],
            _yeni_satirlari(kayit, tablolar, tarih, yazilan),
        ),
        _etf_sayfa(
            kok,
            "etf-tema-haritasi",
            simdi,
            "Tema haritası",
            "Kaldıraçsız ETF'lerin tema başına ortanca getirileri, 1 aylığa göre sıralı.",
            [
                Sutun("tema", "Tema", "metin"),
                Sutun("sayi", "ETF sayısı", "sayi", 0),
                Sutun("g1h", "1 hafta", "yuzde", 1),
                Sutun("g1a", "1 ay", "yuzde", 1),
                Sutun("g3a", "3 ay", "yuzde", 1),
                Sutun("onde", "En güçlü ETF", "metin"),
            ],
            [
                {
                    "tema": t.tema,
                    "sayi": t.sayi,
                    "g1h": t.g1h,
                    "g1a": t.g1a,
                    "g3a": t.g3a,
                    "onde": t.onde,
                }
                for t in ekler.tema_haritasi(dict(olcumler), dict(kayit))
            ],
        ),
        _etf_sayfa(
            kok,
            "etf-temalar",
            simdi,
            "Yükselen temalar",
            "3 aylık getiriye göre en güçlü 20 ETF; aynı hareketi izleyen kopyalar ayıklanmıştır.",
            [
                Sutun("sembol", "Sembol", "metin"),
                Sutun("ad", "Ad", "metin"),
                Sutun("tema", "Tema", "metin"),
                Sutun("g1a", "1 ay", "yuzde", 1),
                Sutun("g3a", "3 ay", "yuzde", 1),
                Sutun("hacim", "Ort. işlem tutarı ($)", "sayi", 0),
            ],
            [
                {
                    "sembol": o.sembol,
                    "ad": adlar.get(o.sembol, o.sembol),
                    "tema": ekler.tema_bul(adlar.get(o.sembol, o.sembol)) or "–",
                    "g1a": o.g1a,
                    "g3a": o.g3a,
                    "hacim": o.dolar_hacim,
                    "seri": _anahtar("etf", o.sembol, yazilan),
                }
                for o in temalar
            ],
        ),
        _etf_sayfa(
            kok,
            "etf-akis",
            simdi,
            "Fon akışı",
            "Fon varlığı değişiminden fiyat etkisi çıkarılarak tahmin edilen giriş ve çıkışlar "
            "(son 5 işlem günü).",
            [
                Sutun("yon", "Yön", "metin"),
                Sutun("sembol", "Sembol", "metin"),
                Sutun("ad", "Ad", "metin"),
                Sutun("akis", "Tahmini akış ($)", "sayi", 0),
                Sutun("oran", "Başlangıç varlığına oran", "yuzde", 1),
            ],
            _akis_satirlari(akis),
            suzgecler=["yon"],
        ),
    ]


def _etf_sayfa(
    kok: Path,
    sayfa: str,
    simdi: datetime.datetime,
    baslik: str,
    aciklama: str,
    sutunlar: list[Sutun],
    satirlar: list[dict[str, object]],
    suzgecler: list[str] | None = None,
) -> Path:
    return _sayfa(
        kok,
        sayfa,
        baslik=baslik,
        aciklama=aciklama,
        guncellendi=simdi,
        kaynaklar=[_YAHOO, _NASDAQ],
        sutunlar=sutunlar,
        satirlar=satirlar,
        suzgecler=suzgecler or [],
    )


def _etf_noktalari(df: pd.DataFrame) -> list[tuple[datetime.date, float]]:
    kapanis = df["Close"].dropna().iloc[-SERI_GUN:]
    return [(d.date(), float(v)) for d, v in zip(kapanis.index, kapanis.to_numpy())]


def _hareketler(
    yol: Path, tarih: str, bugun: Sequence[etf_tarama.Sinyal]
) -> list[tuple[str, str, str]]:
    """(gün, tür, sembol) üçlüleri: kayıttaki son GECMIS_GUN günü ve bugünkü hareketler."""
    kume: set[tuple[str, str, str]] = set()
    if yol.exists():
        with yol.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["tarih"] < tarih:
                    kume.add((r["tarih"], r["tur"], r["sembol"]))
    kume.update((tarih, s.tur, s.sembol) for s in bugun)
    son = set(sorted({g for g, _, _ in kume}, reverse=True)[:GECMIS_GUN])
    return sorted(((g, t, s) for g, t, s in kume if g in son), reverse=True)


def _temalar(
    olcumler: Mapping[str, etf_tarama.Olcum],
    kayit: Mapping[str, etf_liste.Etf],
    tablolar: Mapping[str, pd.DataFrame],
) -> list[etf_tarama.Olcum]:
    duz = sorted(
        (
            o
            for s, o in olcumler.items()
            if o.g3a is not None and s in kayit and not etf_liste.tema_disi_mi(kayit[s])
        ),
        key=lambda o: -(o.g3a or 0.0),
    )
    secilen = etf_tarama.kopyalari_ayikla([o.sembol for o in duz[:TEMA_ADAY]], dict(tablolar))[
        :TEMA_SATIRI
    ]
    return [olcumler[s] for s in secilen]


def _yeni_satirlari(
    kayit: Mapping[str, etf_liste.Etf],
    tablolar: Mapping[str, pd.DataFrame],
    tarih: str,
    yazilan: set[str],
) -> list[dict[str, object]]:
    sinir = (pd.Timestamp(tarih) - pd.Timedelta(days=YENI_GUN)).date().isoformat()
    seyir = {y.sembol: y for y in ekler.yeni_seyir(dict(kayit), dict(tablolar), tarih, tarih)}
    satirlar: list[dict[str, object]] = []
    for e in kayit.values():
        g = e["ilk_gorulme"]
        if not g or not (sinir <= g < tarih):
            continue
        y = seyir.get(e["sembol"])
        satirlar.append(
            {
                "ilk_gorulme": g,
                "sembol": e["sembol"],
                "ad": e["ad"],
                "getiri": y.getiri if y else None,
                "ilk_hacim": y.ilk_hacim if y else None,
                "son_hacim": y.son_hacim if y else None,
                "seri": _anahtar("etf", e["sembol"], yazilan),
            }
        )
    satirlar.sort(key=lambda r: (str(r["ilk_gorulme"]), str(r["sembol"])), reverse=True)
    return satirlar


def _akis_satirlari(akis: Sequence[AkisSatiri]) -> list[dict[str, object]]:
    girenler = sorted((a for a in akis if a.akis > 0), key=lambda a: -a.akis)[:AKIS_SATIRI]
    cikanlar = sorted((a for a in akis if a.akis < 0), key=lambda a: a.akis)[:AKIS_SATIRI]
    return [
        {
            "yon": yon,
            "sembol": a.sembol,
            "ad": a.ad,
            "akis": a.akis,
            "oran": a.oran,
        }
        for yon, grup in (("Giriş", girenler), ("Çıkış", cikanlar))
        for a in grup
    ]
