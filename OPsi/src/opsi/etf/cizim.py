# src/opsi/etf/cizim.py
"""ETF Radarı kartları: liste kartları ve sinyal başına fiyat grafiği (ortak Kâğıt)."""

import datetime

import pandas as pd
from rasathane_ortak import kagit
from rasathane_ortak.kagit import AltPanel, Cizgi, Grafik, Hucre, Isaret, Kart, Satir

from ..kanal.cizim import FIKIR, _sayi, _usd, _yuzde
from .liste import Etf, Guncel
from .tarama import TURLER, Olcum, Sinyal

KAYNAK = "Yahoo Finance · Nasdaq"
GRAFIK_GUN = 252


def _tarih(iso: str) -> str:
    return kagit.tarih_metni(datetime.date.fromisoformat(iso))


def _getiri(x: float | None, vurgu: bool = False) -> Hucre:
    if x is None:
        return Hucre("—", ikincil=True)
    return Hucre(_yuzde(x, 1, True), kalin=vurgu, vurgu=vurgu)


def _fiyat(g: Guncel | None) -> str:
    return "—" if g is None or g["fiyat"] is None else _usd(g["fiyat"])


def yeni_ciz(yeniler: list[Etf], guncel: dict[str, Guncel], tarih: str, bas: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Yeni ETF'ler",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"{_tarih(bas)} sonrası listeye giren {len(yeniler)} ETF",
        sutunlar=("ETF", "Fiyat", "Listeye giriş"),
        satirlar=tuple(
            Satir(
                ust=e["sembol"],
                etiket="kaldıraçlı" if e["kaldirac"] else "",
                alt=e["ad"],
                sag=(
                    Hucre(_fiyat(guncel.get(e["sembol"]))),
                    Hucre(datetime.date.fromisoformat(e["ilk_gorulme"]).strftime("%d.%m")),
                ),
            )
            for e in yeniler
        ),
    )


def temalar_ciz(
    olcumler: list[Olcum], adlar: dict[str, str], spy: Olcum | None, tarih: str, taranan: int
) -> Kart:
    spy_metni = f" · SPY 3 ay {_yuzde(spy.g3a, 1, True)}" if spy and spy.g3a is not None else ""
    return Kart(
        fikir=FIKIR,
        ad="Yükselen Temalar",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"3 aylık getiride önde gelenler · {taranan} likit ETF{spy_metni}",
        sutunlar=("ETF", "Fiyat", "1 ay", "3 ay", "Yılbaşı"),
        satirlar=tuple(
            Satir(
                ust=o.sembol,
                alt=adlar.get(o.sembol, o.sembol),
                sag=(
                    Hucre(_usd(o.kapanis)),
                    _getiri(o.g1a),
                    _getiri(o.g3a, vurgu=True),
                    _getiri(o.gyb),
                ),
            )
            for o in olcumler
        ),
    )


def _seviye_metni(s: Sinyal) -> Hucre:
    if s.tur == "hacim":
        return Hucre(f"{_sayi(s.seviye, 1)}×", kalin=True, vurgu=True)
    return Hucre(_usd(s.seviye), kalin=True, vurgu=True)


_SEVIYE_SUTUNU = {
    "zirve_52": "Önceki zirve",
    "altin": "SMA 200",
    "sma200_yukari": "SMA 200",
    "hacim": "Hacim",
}


def sinyal_listesi_ciz(
    tur: str, sinyaller: list[Sinyal], adlar: dict[str, Etf], tarih: str
) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad=TURLER[tur],
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"Bugün {len(sinyaller)} ETF · güç sırasıyla",
        sutunlar=("ETF", "Kapanış", _SEVIYE_SUTUNU[tur]),
        satirlar=tuple(
            Satir(
                ust=s.sembol,
                etiket="kaldıraçlı" if s.sembol in adlar and adlar[s.sembol]["kaldirac"] else "",
                alt=adlar[s.sembol]["ad"] if s.sembol in adlar else s.sembol,
                sag=(
                    Hucre(_usd(s.kapanis), alt=_yuzde(s.degisim, 2, True)),
                    _seviye_metni(s),
                ),
            )
            for s in sinyaller
        ),
    )


def sinyal_grafigi(s: Sinyal, ad: str, kaldirac: bool, df: pd.DataFrame, tarih: str) -> Grafik:
    tum = df["Close"].astype(float)
    sma200 = tum.rolling(200).mean()
    pencere = df.iloc[-GRAFIK_GUN:]
    gunler = tuple(g.date() for g in pencere.index)
    bugun = gunler[-1]
    alanlar: dict[str, object] = {}
    sma = [(g.date(), float(v)) for g, v in sma200.iloc[-GRAFIK_GUN:].items() if pd.notna(v)]
    if s.tur in ("altin", "sma200_yukari") and len(sma) >= 2:
        sma50 = tum.rolling(50).mean().iloc[-GRAFIK_GUN:]
        cizgiler = [Cizgi(tuple(sma))]
        if s.tur == "altin":
            cizgiler.append(
                Cizgi(
                    tuple((g.date(), float(v)) for g, v in sma50.items() if pd.notna(v)),
                    ikincil=True,
                )
            )
        alanlar["cizgiler"] = tuple(c for c in cizgiler if len(c.noktalar) >= 2)
    if s.tur == "zirve_52":
        alanlar["yataylar"] = ((s.seviye, "önceki zirve"),)
    ozet: list[tuple[str, Hucre]] = [
        ("Kapanış", Hucre(_usd(s.kapanis), kalin=True)),
        ("Günlük", Hucre(_yuzde(s.degisim, 2, True), kalin=True, vurgu=True)),
    ]
    if s.tur == "hacim":
        ozet.append(("Hacim / 50g ort.", Hucre(f"{_sayi(s.seviye, 1)}×", kalin=True)))
    else:
        ozet.append((_SEVIYE_SUTUNU[s.tur], Hucre(_usd(s.seviye), kalin=True)))
    return Grafik(
        fikir=FIKIR,
        tarih=_tarih(tarih),
        baslik=f"{s.sembol} · {TURLER[s.tur]}",
        alt_baslik=ad + (" · kaldıraçlı" if kaldirac else ""),
        ozet=tuple(ozet),
        gunler=gunler,
        seri=tuple(float(v) for v in pencere["Close"]),
        kaynak=KAYNAK,
        isaretler=(Isaret(bugun, ""),),
        alt_panel=AltPanel(
            "hacim", tuple(float(v) for v in pencere["Volume"].fillna(0)), vurgu_gun=bugun
        ),
        **alanlar,  # type: ignore[arg-type]
    )


def etiket(sembol: str) -> str:
    return "#" + sembol.replace("-", "_").replace(".", "_")
