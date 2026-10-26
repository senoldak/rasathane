"""INseeder fiyat grafiği kartı: günün en büyük içeriden alımının son üç aylık fiyatı."""
from collections import OrderedDict
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from inseeder.kanal.bicim import fiyat, para
from inseeder.kanal.kartlar import FIKIR
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Grafik, Hucre, Isaret
from inseeder.kanal.secim import Satir

FiyatCekici = Callable[[str, date, date], List[Tuple[date, float]]]
AD = "Fiyat Grafiği"
KAYNAK = "SEC EDGAR · Yahoo Finance"
AZAMI_SAPMA = 0.25  # alım fiyatı kapanıştan bu kadar saparsa açık piyasa dışı işlem sayılır
GUN_SAYISI = 92


def yahoo_kapanislar(sembol: str, bas: date, son: date) -> List[Tuple[date, float]]:
    import yfinance as yf  # yalnız gerçek koşuda; testler sahte çekici kullanır

    h = yf.Ticker(sembol).history(start=bas.isoformat(), end=son.isoformat(), auto_adjust=False)["Close"]
    return [(i.date(), float(v)) for i, v in h.items() if v == v]


def _gruplar(satirlar: List[Satir]) -> "OrderedDict[str, List[Satir]]":
    gruplar: Dict[str, List[Satir]] = {}
    for s in satirlar:
        gruplar.setdefault(s.beyan.sembol, []).append(s)
    sirali = sorted(gruplar.items(), key=lambda kv: -sum(s.beyan.tutar for s in kv[1]))
    return OrderedDict(sirali)


def _alim_fiyati(satirlar: List[Satir]) -> float:
    toplam = sum(s.beyan.tutar for s in satirlar)
    return sum(s.beyan.ort_fiyat * s.beyan.tutar for s in satirlar) / toplam


def grafik_secimi(satirlar: List[Satir], kapanis: Callable[[str], Optional[float]]) -> Optional[str]:
    """Toplam tutarı en büyük sembol; alım fiyatı beyan günü kapanışından %25'ten fazla saparsa sıradaki."""
    for sembol, grup in _gruplar(satirlar).items():
        k = kapanis(sembol)
        if k and abs(_alim_fiyati(grup) / k - 1) <= AZAMI_SAPMA:
            return sembol
    return None


def _fark(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}%{abs(x) * 100:.1f}".replace(".", ",")


def grafik_karti(gun: date, sembol: str, satirlar: List[Satir], fiyatlar: List[Tuple[date, float]]) -> Grafik:
    grup = [s for s in satirlar if s.beyan.sembol == sembol]
    seri = [(g, v) for g, v in fiyatlar if gun - timedelta(days=GUN_SAYISI) <= g <= gun]
    alim = _alim_fiyati(grup)
    son = seri[-1][1]
    unvanlar = ", ".join(OrderedDict.fromkeys(s.beyan.unvan for s in grup))
    return Grafik(
        fikir=FIKIR, tarih=kagit.tarih_metni(gun), baslik=f"{sembol} · {grup[0].beyan.sirket}",
        alt_baslik=f"{unvanlar} · {para(sum(s.beyan.tutar for s in grup))}",
        ozet=(("Son kapanış", Hucre(f"${fiyat(son)}")), ("Alım fiyatı", Hucre(f"${fiyat(alim)}", vurgu=True)),
              ("Fark", Hucre(_fark(son / alim - 1)))),
        gunler=tuple(g for g, _ in seri), seri=tuple(v for _, v in seri), kaynak=KAYNAK,
        yatay=alim, yatay_etiket=f"alım ${fiyat(alim)}",
        isaretler=(Isaret(gun, f"beyan {gun:%d.%m}"),),
    )
