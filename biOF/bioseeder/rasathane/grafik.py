"""biOF Olay Grafiği: sabah bültenindeki en önemli olayın son üç aylık fiyat seyri."""
from datetime import date, timedelta
from typing import Callable, List, Tuple

from bioseeder.rasathane.kart import FIKIR
from bioseeder.rasathane.olay import Olay
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Grafik, Hucre, Isaret

AD = "Olay Grafiği"
GUN_SAYISI = 92
FiyatCekici = Callable[[str, date, date], List[Tuple[date, float]]]


def yahoo_kapanislar(ticker: str, bas: date, son: date) -> List[Tuple[date, float]]:
    import yfinance as yf  # yalnız gerçek koşuda; testler sahte çekici kullanır

    h = yf.Ticker(ticker).history(start=bas.isoformat(), end=son.isoformat(), auto_adjust=False)["Close"]
    return [(i.date(), float(v)) for i, v in h.items() if v == v]


def _fiyat(x: float) -> str:
    return f"${x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _degisim(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}%{abs(x) * 100:.1f}".replace(".", ",")


def olay_grafigi(o: Olay, sirket: str, tarih_metni: str, fiyatlar: List[Tuple[date, float]]) -> Grafik:
    seri = [(g, v) for g, v in fiyatlar if o.tarih - timedelta(days=GUN_SAYISI) <= g <= o.tarih]
    gunler = [g for g, _ in seri]
    if o.tarih not in gunler or len(seri) < 2:
        raise ValueError(f"{o.ticker} için {o.tarih:%d.%m.%Y} kapanışı yok")
    once, olay_gunu = seri[-2][1], seri[-1][1]
    sec = "sec.gov" in (o.baglanti or "")  # ClinicalTrials.gov olaylarının bağlantısı da dolu
    kaynak = "SEC EDGAR" if sec else "ClinicalTrials.gov"
    belge = "SEC 8-K" if sec else "ClinicalTrials.gov"
    return Grafik(
        fikir=FIKIR, tarih=tarih_metni, baslik=f"{o.ticker} · {sirket}" if sirket else o.ticker,
        alt_baslik=f"{o.etiket} · {belge}, {o.tarih:%d.%m.%Y}",
        ozet=(("Önceki kapanış", Hucre(_fiyat(once))), ("Olay günü", Hucre(_fiyat(olay_gunu), vurgu=True)),
              ("Değişim", Hucre(_degisim(olay_gunu / once - 1)))),
        gunler=tuple(gunler), seri=tuple(v for _, v in seri), kaynak=f"{kaynak} · Yahoo Finance",
        isaretler=(Isaret(o.tarih, o.etiket),),
    )
