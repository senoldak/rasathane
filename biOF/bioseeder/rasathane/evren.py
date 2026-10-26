import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from bioseeder.rasathane.ayar import EK
from bioseeder.rasathane.http import Istemci, KaynakHatasi

BORSALAR = {"Nasdaq", "NYSE", "NYSE American"}
SIC_KODLARI = {2834, 2836}  # ilaç; biyolojik ürün
MIKRO_ESIK_M = 50.0
AZAMI_YAS_GUN = 45

_EKLER = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
    "llc", "lp", "nv", "sa", "ag", "se", "holdings", "group",
}


@dataclass
class Sirket:
    ticker: str
    cik: int
    ad: str
    borsa: str
    sic: int
    piyasa_degeri_m: Optional[float]

    @property
    def mikro(self) -> bool:
        return self.piyasa_degeri_m is None or self.piyasa_degeri_m < MIKRO_ESIK_M


def ad_normallestir(ad: str) -> str:
    s = ad.lower().replace("&", " and ")
    s = re.sub(r"\b([a-z])\.\s?([a-z])\.", r"\1\2", s)  # "N.V." → "nv", "S.A." → "sa"
    kelimeler = re.sub(r"[^a-z0-9]+", " ", s).split()
    while kelimeler and kelimeler[-1] in _EKLER:
        kelimeler.pop()
    return " ".join(kelimeler)


def _ek_oku(ek_yolu: Path) -> List[Dict[str, str]]:
    if not ek_yolu.exists():
        return []
    with ek_yolu.open(encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def evren_olustur(
    ist: Istemci,
    piyasa_degeri: Callable[[str], Optional[float]],
    eski: Optional[Dict[int, int]] = None,
    ek_yolu: Path = EK,
) -> List[Sirket]:
    eski = eski or {}
    ek = _ek_oku(ek_yolu)
    zorla = {r["ticker"].upper() for r in ek if r.get("islem") == "ekle"}
    veri = ist.json("https://www.sec.gov/files/company_tickers_exchange.json", sec=True)
    alanlar = veri["fields"]
    sirketler: List[Sirket] = []
    gorulen = set()
    for satir in veri["data"]:
        k = dict(zip(alanlar, satir))
        ticker = str(k["ticker"]).upper()
        if k["exchange"] not in BORSALAR or ticker in gorulen:
            continue
        cik = int(k["cik"])
        sic = eski.get(cik)
        if sic is None:
            sub = ist.json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", sec=True)
            sic = int(sub.get("sic") or 0)
        if sic not in SIC_KODLARI and ticker not in zorla:
            continue
        gorulen.add(ticker)
        sirketler.append(Sirket(ticker, cik, k["name"], k["exchange"], sic, piyasa_degeri(ticker)))
    return ek_uygula(sirketler, ek_yolu)[0]


def ek_uygula(sirketler: List[Sirket], ek_yolu: Path) -> Tuple[List[Sirket], Dict[str, str]]:
    ek = _ek_oku(ek_yolu)
    cikar = {r["ticker"].upper() for r in ek if r.get("islem") == "cikar"}
    esle = {ad_normallestir(r["ad"]): r["ticker"].upper() for r in ek if r.get("islem") == "esle" and r.get("ad")}
    return [s for s in sirketler if s.ticker not in cikar], esle


def sponsor_eslestir(sirketler: List[Sirket], esle: Dict[str, str]) -> Dict[str, Sirket]:
    tickerdan = {s.ticker: s for s in sirketler}
    sonuc = {ad_normallestir(s.ad): s for s in sirketler}
    for ad, ticker in esle.items():
        if ticker in tickerdan:
            sonuc[ad_normallestir(ad)] = tickerdan[ticker]
    return sonuc


_ALANLAR = ["ticker", "cik", "ad", "borsa", "sic", "piyasa_degeri_m"]


def evren_yaz(sirketler: List[Sirket], yol: Path, bugun: Optional[date] = None) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    with yol.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# olusturma: {(bugun or date.today()).isoformat()}\n")
        w = csv.writer(f)
        w.writerow(_ALANLAR)
        for s in sorted(sirketler, key=lambda x: x.ticker):
            w.writerow([s.ticker, s.cik, s.ad, s.borsa, s.sic,
                        "" if s.piyasa_degeri_m is None else f"{s.piyasa_degeri_m:.2f}"])


def evren_oku(yol: Path, bugun: Optional[date] = None) -> List[Sirket]:
    hata = "Evren dosyası eski ya da yok; 'evren' işini çalıştırın"
    if not yol.exists():
        raise KaynakHatasi(hata)
    with yol.open(encoding="utf-8", newline="") as f:
        ilk = f.readline()
        m = re.match(r"# olusturma: (\d{4}-\d{2}-\d{2})", ilk)
        if not m or ((bugun or date.today()) - date.fromisoformat(m.group(1))).days > AZAMI_YAS_GUN:
            raise KaynakHatasi(hata)
        return [
            Sirket(r["ticker"], int(r["cik"]), r["ad"], r["borsa"], int(r["sic"]),
                   float(r["piyasa_degeri_m"]) if r["piyasa_degeri_m"] else None)
            for r in csv.DictReader(f)
        ]


def yahoo_piyasa_degeri(ticker: str) -> Optional[float]:
    try:
        import yfinance as yf

        deger = yf.Ticker(ticker).fast_info["market_cap"]
        return round(float(deger) / 1e6, 2) if deger else None
    except Exception:
        return None
