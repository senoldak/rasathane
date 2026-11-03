"""Site verisi: kartları besleyen sonuçlardan `site-veri/emtia/` JSON dosyaları."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz, seri_cok_yaz, seri_yaz

from .evren import ADLAR, DOLAR_ENDEKSI, EMTIALAR, USDTRY
from .merkez_altin import aktar as merkez_aktar
from .raporlar import Pozisyon, Stok
from .tarama import TURLER, Olcum, OranOlcum, Sinyal, olc, sinyaller

log = logging.getLogger("emtia")

BOLUM = "emtia"
SERI_GUN = 252
HAFTA_SAYI = 104
_YAHOO = Kaynak("Yahoo Finance", "https://finance.yahoo.com/")
_EIA = Kaynak("EIA", "https://www.eia.gov/")
_CFTC = Kaynak("CFTC", "https://www.cftc.gov/")
_DIGER = "Döviz ve endeks"


def _sayfa(*a: Any, **k: Any) -> Path:
    return Path(sayfa_yaz(*a, **k))


def _gun(i: Any) -> datetime.date:
    return pd.Timestamp(i).date()


def _noktalar(s: pd.Series) -> list[tuple[datetime.date, float]]:
    s = s.astype(float).dropna().iloc[-SERI_GUN:]
    return [(_gun(i), float(v)) for i, v in s.items()]


def _seri_anahtari(onek: str, ham: str) -> str:
    return f"{onek}-{ham.replace('_', '-')}"


def _sec(df: pd.DataFrame, n: int) -> tuple[list[datetime.date], dict[str, list[float | None]]]:
    tarihler = [_gun(i) for i in df.index]
    sutunlar = {k: [None if pd.isna(v) else float(v) for v in df[k]] for k in df.columns}
    return tarihler[-n:], {k: v[-n:] for k, v in sutunlar.items()}


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    """Wilder RSI (yumuşatma alpha = 1/n)."""
    fark = c.diff()
    kazanc = fark.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    kayip = (-fark.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + kazanc / kayip)


def _fiyat_serisi(
    kok: Path,
    anahtar: str,
    ad: str,
    birim: str,
    kapanis: pd.Series,
    isaretler: list[tuple[datetime.date, str]] | None = None,
    df: pd.DataFrame | None = None,
) -> None:
    """Ortak gösterge seti (tüm sayfalar): EMA 144/233/377, Kijun-sen (26), RSI (14).

    Günlük seri son 1 yıl, haftalık seri son 2 yıl yazılır; göstergeler tam geçmiş üzerinde
    hesaplanır, böylece ısınma sorunu olmaz. Kijun için yüksek/düşük gerekir (gram ve döviz yok).
    """
    c = kapanis.astype(float).dropna()
    hi: pd.Series | None = None
    lo: pd.Series | None = None
    if df is not None and {"High", "Low"} <= set(df.columns):
        hi = df["High"].astype(float).reindex(c.index)
        lo = df["Low"].astype(float).reindex(c.index)

    gunluk = pd.DataFrame(
        {
            "kapanis": c,
            "ema144": c.ewm(span=144, adjust=False).mean(),
            "ema233": c.ewm(span=233, adjust=False).mean(),
            "ema377": c.ewm(span=377, adjust=False).mean(),
            "rsi14": _rsi(c),
        }
    )
    if hi is not None and lo is not None:
        gunluk["kijun"] = (hi.rolling(26).max() + lo.rolling(26).min()) / 2
    t, s = _sec(gunluk, SERI_GUN)
    seri_cok_yaz(kok, BOLUM, anahtar, t, s, ad=ad, birim=birim, isaretler=isaretler or [])

    h = c.resample("W-FRI").last().dropna()
    haftalik = pd.DataFrame(
        {
            "kapanis": h,
            "ema144": h.ewm(span=144, adjust=False).mean(),
            "ema233": h.ewm(span=233, adjust=False).mean(),
            "rsi14": _rsi(h),
        }
    )
    if hi is not None and lo is not None:
        whi = hi.resample("W-FRI").max().reindex(h.index)
        wlo = lo.resample("W-FRI").min().reindex(h.index)
        haftalik["kijun"] = (whi.rolling(26).max() + wlo.rolling(26).min()) / 2
    t, s = _sec(haftalik, HAFTA_SAYI)
    seri_cok_yaz(
        kok, BOLUM, f"{anahtar}-hafta", t, s, ad=ad, birim=birim, isaretler=isaretler or []
    )


def _pano(
    kok: Path,
    simdi: datetime.datetime,
    bugunku: dict[str, pd.DataFrame],
    olcumler: dict[str, Olcum],
    gram: pd.Series | None,
    gram_olcum: Olcum | None,
) -> Path:
    satirlar: list[dict[str, object]] = []

    def ekle(
        anahtar: str,
        ad: str,
        grup: str,
        birim: str,
        o: Olcum,
        seri: pd.Series,
        df: pd.DataFrame | None = None,
    ) -> None:
        satirlar.append(
            {
                "ad": ad,
                "grup": grup,
                "kapanis": o.kapanis,
                "gunluk": o.gunluk,
                "g1h": o.g1h,
                "g1a": o.g1a,
                "gyb": o.gyb,
                "birim": birim,
                "seri": anahtar,
            }
        )
        _fiyat_serisi(kok, anahtar, ad, birim, seri, df=df)

    for e in EMTIALAR:
        if e.sembol in olcumler and e.sembol in bugunku:
            ekle(
                e.sembol,
                e.ad,
                e.grup,
                e.birim,
                olcumler[e.sembol],
                bugunku[e.sembol]["Close"],
                bugunku[e.sembol],
            )
    if gram is not None and gram_olcum is not None:
        ekle("gram", "Gram altın", "Değerli metaller", "₺/gram", gram_olcum, gram)
    for sembol, ad, birim in ((USDTRY, "USD/TRY", "₺"), (DOLAR_ENDEKSI, "Dolar endeksi", "puan")):
        if sembol in olcumler and sembol in bugunku:
            ekle(sembol, ad, _DIGER, birim, olcumler[sembol], bugunku[sembol]["Close"])
    return _sayfa(
        kok,
        BOLUM,
        "pano",
        baslik="Emtia panosu",
        aciklama="20 emtianın ön ay vadeli fiyatı; gram altın, USD/TRY ve dolar endeksi.",
        guncellendi=simdi,
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Ad", "metin"),
            Sutun("grup", "Grup", "metin"),
            Sutun("kapanis", "Kapanış", "sayi", 2),
            Sutun("gunluk", "Günlük", "yuzde", 1),
            Sutun("g1h", "1 hafta", "yuzde", 1),
            Sutun("g1a", "1 ay", "yuzde", 1),
            Sutun("gyb", "Yılbaşından beri", "yuzde", 1),
            Sutun("birim", "Birim", "metin"),
        ],
        satirlar=satirlar,
        suzgecler=["grup"],
    )


GECMIS_GUN = 90


def _gecmis_hareketler(bugunku: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    """Son GECMIS_GUN işlem gününün hareketlerini, her koşuda 5 yıllık veriden yeniden hesaplar.

    Geçmiş birikmez; her koşu aynı kuralla baştan üretir, böylece tutarsızlık birikmez.
    Aynı gün ve emtiadaki birden çok hareket tek satırda, türleri "·" ile ayrılmış olur.
    """
    kayit: dict[tuple[str, str], dict[str, object]] = {}
    for e in EMTIALAR:
        df = bugunku.get(e.sembol)
        if df is None or len(df) < 2:
            continue
        for k in range(max(1, len(df) - GECMIS_GUN), len(df)):
            alt = df.iloc[: k + 1]
            o = olc(e.sembol, alt)
            if o is None:
                continue
            gun = _gun(alt.index[-1]).isoformat()
            for sy in sinyaller(e.sembol, alt, o):
                tur_ad = TURLER[sy.tur]
                anahtar = (gun, e.sembol)
                if anahtar in kayit:
                    kayit[anahtar]["tur"] = f"{kayit[anahtar]['tur']} · {tur_ad}"
                else:
                    kayit[anahtar] = {
                        "tarih": gun,
                        "ad": e.ad,
                        "tur": tur_ad,
                        "kapanis": sy.kapanis,
                        "gunluk": sy.gunluk,
                        "seri": e.sembol,
                    }
    return sorted(kayit.values(), key=lambda r: (str(r["tarih"]), str(r["ad"])), reverse=True)


def _hareketler(
    kok: Path,
    simdi: datetime.datetime,
    bugunku: dict[str, pd.DataFrame],
) -> Path:
    satirlar = _gecmis_hareketler(bugunku)
    # Her emtianın seri grafiğinde son 90 günün hareket işaretleri.
    isaretler: dict[str, list[tuple[datetime.date, str]]] = {}
    for r in satirlar:
        isaretler.setdefault(str(r["seri"]), []).append(
            (datetime.date.fromisoformat(str(r["tarih"])), str(r["tur"]))
        )
    for sembol, liste in isaretler.items():
        if sembol not in bugunku:
            continue
        e = ADLAR.get(sembol)
        _fiyat_serisi(
            kok,
            sembol,
            e.ad if e else sembol,
            e.birim if e else "",
            bugunku[sembol]["Close"],
            liste,
            df=bugunku[sembol],
        )
    return _sayfa(
        kok,
        BOLUM,
        "hareketler",
        baslik="Hareketler",
        aciklama="Son 90 işlem gününde günlük getirisi 60 günlük oynaklığın 2,5 katını aşan "
        "emtialar ve 52 hafta zirve ya da dibini aşanlar.",
        guncellendi=simdi,
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("tarih", "Tarih", "tarih"),
            Sutun("ad", "Emtia", "metin"),
            Sutun("tur", "Hareket", "metin"),
            Sutun("kapanis", "Kapanış", "sayi", 2),
            Sutun("gunluk", "Günlük", "yuzde", 1),
        ],
        satirlar=satirlar,
    )


def _stoklar(kok: Path, simdi: datetime.datetime, rapor: dict[str, Any]) -> Path | None:
    stoklar: list[Stok] = [*rapor.get("eia_petrol", []), *rapor.get("eia_gaz", [])]
    if not stoklar:
        return None
    satirlar: list[dict[str, object]] = []
    for s in stoklar:
        anahtar = _seri_anahtari("eia", s.seri.seri)
        satirlar.append(
            {
                "ad": s.seri.ad,
                "donem": s.donem,
                "deger": s.deger,
                "degisim": s.degisim,
                "yil_once": s.yil_once,
                "birim": s.seri.birim,
                "seri": anahtar,
            }
        )
        noktalar = [(datetime.date.fromisoformat(d), v) for d, v in reversed(s.gecmis)]
        seri_yaz(kok, BOLUM, anahtar, noktalar, ad=s.seri.ad, birim=s.seri.birim)
    return _sayfa(
        kok,
        BOLUM,
        "stoklar",
        baslik="EIA stokları",
        aciklama="ABD haftalık petrol stokları ve doğalgaz depoları.",
        guncellendi=simdi,
        kaynaklar=[_EIA],
        sutunlar=[
            Sutun("ad", "Kalem", "metin"),
            Sutun("donem", "Rapor haftası", "tarih"),
            Sutun("deger", "Stok", "sayi", 1),
            Sutun("degisim", "Haftalık değişim", "sayi", 1),
            Sutun("yil_once", "1 yıl önce", "sayi", 1),
            Sutun("birim", "Birim", "metin"),
        ],
        satirlar=satirlar,
    )


def _fonlar(kok: Path, simdi: datetime.datetime, rapor: dict[str, Any]) -> Path | None:
    pozisyonlar: list[Pozisyon] = list(rapor.get("cot", []))
    if not pozisyonlar:
        return None
    satirlar: list[dict[str, object]] = []
    for p in pozisyonlar:
        e = ADLAR.get(p.sembol)
        ad = e.ad if e else p.sembol
        anahtar = f"cftc-{p.sembol}"
        satirlar.append(
            {
                "ad": ad,
                "donem": p.donem,
                "net": p.net,
                "degisim": p.degisim,
                "yuzdelik": p.yuzdelik,
                "acik": p.acik,
                "uc": "Uç değer" if p.uc else "",
                "seri": anahtar,
            }
        )
        noktalar = [(datetime.date.fromisoformat(d), float(n)) for d, n in reversed(p.gecmis)]
        seri_yaz(kok, BOLUM, anahtar, noktalar, ad=f"{ad} net pozisyon", birim="kontrat")
    return _sayfa(
        kok,
        BOLUM,
        "fonlar",
        baslik="Fon pozisyonları",
        aciklama="CFTC raporunda yönetilen fonların net pozisyonu ve son 3 yıldaki dilimi.",
        guncellendi=simdi,
        kaynaklar=[_CFTC],
        sutunlar=[
            Sutun("ad", "Emtia", "metin"),
            Sutun("donem", "Rapor tarihi", "tarih"),
            Sutun("net", "Net pozisyon", "sayi", 0),
            Sutun("degisim", "Haftalık değişim", "sayi", 0),
            Sutun("yuzdelik", "3 yıllık dilim", "yuzde", 0),
            Sutun("acik", "Açık pozisyon", "sayi", 0),
            Sutun("uc", "Durum", "metin"),
        ],
        satirlar=satirlar,
    )


def aktar(
    kok: Path,
    simdi: datetime.datetime,
    tarih: str,
    bugunku: dict[str, pd.DataFrame],
    olcumler: dict[str, Olcum],
    gram: pd.Series | None,
    gram_olcum: Olcum | None,
    oran_olcumleri: list[OranOlcum],
    hareketler: list[Sinyal],
    rapor: dict[str, Any],
) -> list[Path]:
    """`kok / "emtia"` altına sayfaları ve serileri yazar; yazılan sayfa yollarını döndürür."""
    yollar = [
        _pano(kok, simdi, bugunku, olcumler, gram, gram_olcum),
        _hareketler(kok, simdi, bugunku),
    ]
    for yazici in (_stoklar, _fonlar):
        yol = yazici(kok, simdi, rapor)
        if yol is not None:
            yollar.append(yol)
    merkez = merkez_aktar(kok, simdi)
    if merkez is not None:
        yollar.append(merkez)
    return yollar
