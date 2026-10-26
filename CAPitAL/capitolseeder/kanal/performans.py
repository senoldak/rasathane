"""Beyan edilen alımlardan sonra hisselerin SPY'ye göre ne yaptığı."""
import datetime
import logging
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import yfinance as yf

from capitolseeder.kanal.model import Beyan, hisse_mi

logger = logging.getLogger("capitolseeder.kanal")

Fiyatlar = dict[str, list[tuple[datetime.date, float]]]
KARSILASTIRMA = "SPY"
AZAMI_BOSLUK = 5  # gün: işlemden sonraki ilk kapanış ve son kapanış bu kadar yakın olmalı
AZAMI_EKSIK_ORANI = 0.2  # fiyatı hiç gelmeyen alım oranı bunu geçerse kart çıkmaz


class FiyatHatasi(Exception):
    pass


@dataclass
class UyePerformansi:
    uye: str
    parti: str
    eyalet: str
    meclis: str
    alim_sayisi: int
    ort_degisim: float
    ort_spy: float
    fark: float
    spy_ustu_oran: float


def _yahoo(sembol: str) -> str:
    return sembol.replace(".", "-")


def fiyatlari_cek(semboller: list[str], baslangic: datetime.date) -> Fiyatlar:
    istek = sorted({_yahoo(s) for s in semboller} | {KARSILASTIRMA})
    geri = {_yahoo(s): s for s in semboller}
    tablo = yf.download(
        istek,
        start=baslangic.isoformat(),
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    sonuc: Fiyatlar = {}
    if tablo is None or tablo.empty:
        return sonuc
    for y in istek:
        try:
            seri = tablo[y]["Close"].dropna()
        except KeyError:
            continue
        if seri.empty:
            continue
        sonuc[geri.get(y, y)] = [(t.date(), float(v)) for t, v in seri.items()]
    return sonuc


def degisim(f: list[tuple[datetime.date, float]], baslangic: datetime.date) -> Optional[float]:
    if not f:
        return None
    i = bisect_left([t for t, _ in f], baslangic)
    if i >= len(f) - 1:
        return None
    ilk, son = f[i][1], f[-1][1]
    if not ilk:
        return None
    return (son / ilk - 1) * 100


def pencere_baslangici(beyanlar: list[Beyan], bugun: datetime.date) -> datetime.date:
    yil_once = bugun - datetime.timedelta(days=365)
    if not beyanlar:
        return yil_once
    return max(yil_once, min(b.beyan_tarihi for b in beyanlar))


def _olc(
    hisse: list[tuple[datetime.date, float]],
    spy: list[tuple[datetime.date, float]],
    islem: datetime.date,
    bugun: datetime.date,
) -> Optional[tuple[float, float]]:
    """Hisse ve SPY'nin aynı başlangıç ve bitiş kapanışları arasındaki yüzde değişimi."""
    tarihler = [t for t, _ in hisse]
    i = bisect_left(tarihler, islem)
    if i >= len(hisse) - 1:
        return None
    bas, bit = tarihler[i], tarihler[-1]
    if (bas - islem).days > AZAMI_BOSLUK or (bugun - bit).days > AZAMI_BOSLUK:
        return None  # seri işlemden çok sonra başlıyor ya da kotasyon bitmiş
    spy_tarihleri = [t for t, _ in spy]
    j = bisect_left(spy_tarihleri, bas)
    k = bisect_left(spy_tarihleri, bit + datetime.timedelta(days=1)) - 1
    if j >= len(spy) or k <= j or not hisse[i][1] or not spy[j][1]:
        return None
    return (hisse[-1][1] / hisse[i][1] - 1) * 100, (spy[k][1] / spy[j][1] - 1) * 100


def performans(
    beyanlar: list[Beyan], fiyatlar: Fiyatlar, bugun: datetime.date, en_az: int = 5
) -> tuple[list[UyePerformansi], list[UyePerformansi], datetime.date]:
    spy = fiyatlar.get(KARSILASTIRMA)
    if not spy:
        raise FiyatHatasi("SPY fiyatları alınamadı.")
    baslangic = pencere_baslangici(beyanlar, bugun)
    uyeler: dict[str, list[Beyan]] = defaultdict(list)
    for b in beyanlar:
        if b.yon == "Alış" and hisse_mi(b) and b.beyan_tarihi >= baslangic:
            uyeler[b.uye].append(b)

    tum = [b for a in uyeler.values() for b in a]
    eksik = sum(1 for b in tum if b.ticker not in fiyatlar)
    if tum and eksik / len(tum) > AZAMI_EKSIK_ORANI:
        raise FiyatHatasi(f"Alımların {eksik}/{len(tum)} tanesi için fiyat gelmedi.")

    sonuclar: list[UyePerformansi] = []
    for uye, alimlar in uyeler.items():
        olculen: list[tuple[float, float]] = []
        for b in alimlar:
            o = _olc(fiyatlar.get(b.ticker, []), spy, b.islem_tarihi, bugun)
            if o is not None:
                olculen.append(o)
        if len(olculen) < en_az or len(olculen) * 2 < len(alimlar):
            continue
        ort_d = sum(d for d, _ in olculen) / len(olculen)
        ort_s = sum(s for _, s in olculen) / len(olculen)
        ilk = alimlar[0]
        sonuclar.append(
            UyePerformansi(
                uye=uye,
                parti=ilk.parti,
                eyalet=ilk.eyalet,
                meclis=ilk.meclis,
                alim_sayisi=len(olculen),
                ort_degisim=ort_d,
                ort_spy=ort_s,
                fark=ort_d - ort_s,
                spy_ustu_oran=sum(1 for d, s in olculen if d > s) / len(olculen),
            )
        )
    if not sonuclar:
        raise FiyatHatasi("Performans kartı için uygun üye yok.")
    sonuclar.sort(key=lambda p: -p.fark)
    if len(sonuclar) >= 10:
        return sonuclar[:5], sorted(sonuclar[-5:], key=lambda p: p.fark), baslangic
    yari = (len(sonuclar) + 1) // 2
    return sonuclar[:yari], sorted(sonuclar[yari:], key=lambda p: p.fark), baslangic
