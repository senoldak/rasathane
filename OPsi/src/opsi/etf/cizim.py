# src/opsi/etf/cizim.py
"""ETF Radarı kartları: liste kartları ve sinyal başına fiyat grafiği (ortak Kâğıt)."""

import datetime

import pandas as pd
from rasathane_ortak import kagit
from rasathane_ortak.kagit import AltPanel, Bolum, Cizgi, Grafik, Hucre, Isaret, Kart, Satir

from ..kanal.cizim import FIKIR, _sayi, _usd, _yuzde
from .ekler import AkisSatiri, OpsiyonSatiri, RejimSatiri, TemaSatiri, YeniSeyir
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
        sutunlar=("ETF", "1 ay", "3 ay", "Yılbaşı"),
        satirlar=tuple(
            Satir(
                ust=o.sembol,
                alt=adlar.get(o.sembol, o.sembol),
                sag=(
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
    if s.tur == "rs_zirve":
        return Hucre(_yuzde(s.seviye, 1, True), kalin=True, vurgu=True)
    return Hucre(_usd(s.seviye), kalin=True, vurgu=True)


_SEVIYE_SUTUNU = {
    "zirve_52": "Önceki zirve",
    "altin": "SMA 200",
    "sma200_yukari": "SMA 200",
    "hacim": "Hacim",
    "rs_zirve": "Fiyat zirveye",
    "dip_52": "Önceki dip",
    "olum": "SMA 200",
    "sma200_asagi": "SMA 200",
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
    if s.tur in ("altin", "olum", "sma200_yukari", "sma200_asagi") and len(sma) >= 2:
        sma50 = tum.rolling(50).mean().iloc[-GRAFIK_GUN:]
        cizgiler = [Cizgi(tuple(sma))]
        if s.tur in ("altin", "olum"):
            cizgiler.append(
                Cizgi(
                    tuple((g.date(), float(v)) for g, v in sma50.items() if pd.notna(v)),
                    ikincil=True,
                )
            )
        alanlar["cizgiler"] = tuple(c for c in cizgiler if len(c.noktalar) >= 2)
    if s.tur == "zirve_52":
        alanlar["yataylar"] = ((s.seviye, "önceki zirve"),)
    elif s.tur == "dip_52":
        alanlar["yataylar"] = ((s.seviye, "önceki dip"),)
    elif s.tur == "rs_zirve":
        alanlar["yataylar"] = ((s.kapanis / (1 + s.seviye), "52 hafta zirvesi"),)
    ozet: list[tuple[str, Hucre]] = [
        ("Kapanış", Hucre(_usd(s.kapanis), kalin=True)),
        ("Günlük", Hucre(_yuzde(s.degisim, 2, True), kalin=True, vurgu=True)),
    ]
    if s.tur == "hacim":
        ozet.append(("Hacim / 50g ort.", Hucre(f"{_sayi(s.seviye, 1)}×", kalin=True)))
    elif s.tur == "rs_zirve":
        ozet.append(("Fiyat zirveye", Hucre(_yuzde(s.seviye, 1, True), kalin=True)))
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


def _tutar(x: float) -> str:
    """Büyük dolar tutarı: $1,2 Mr / $340 Mn."""
    m = abs(x)
    isaret = "−" if x < 0 else ""
    if m >= 1e9:
        return f"{isaret}${_sayi(m / 1e9, 1)} Mr"
    return f"{isaret}${_sayi(m / 1e6, 0 if m >= 1e7 else 1)} Mn"


def tema_haritasi_ciz(satirlar: list[TemaSatiri], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Tema Haritası",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="Tema başına ortanca getiri · kaldıraçsız likit ETF'ler · 1 aya göre sıralı",
        sutunlar=("Tema", "1 hafta", "1 ay", "3 ay"),
        satirlar=tuple(
            Satir(
                ust=r.tema,
                alt=f"{r.sayi} ETF · önde {r.onde}",
                sag=(_getiri(r.g1h), _getiri(r.g1a, vurgu=True), _getiri(r.g3a)),
            )
            for r in satirlar
        ),
    )


def rejim_ciz(satirlar: list[RejimSatiri], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Piyasa Rejimi",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="ETF oranları · oran yükseliyorsa alttaki anlam güçleniyor",
        sutunlar=("Oran", "1 ay", "SMA 50"),
        satirlar=tuple(
            Satir(
                ust=f"{r.pay}/{r.payda}",
                alt=f"{r.ad} · {r.anlam}",
                sag=(
                    _getiri(r.g1a, vurgu=True),
                    Hucre("üstünde" if r.sma50_ustu else "altında", ikincil=not r.sma50_ustu),
                ),
            )
            for r in satirlar
        ),
    )


def yeni_seyir_ciz(satirlar: list[YeniSeyir], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Yeni ETF'lerin Seyri",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="Son 45 günde listelenenler · işlem tutarı büyümesine göre",
        sutunlar=("ETF", "Getiri", "Günlük tutar"),
        satirlar=tuple(
            Satir(
                ust=r.sembol,
                alt=r.ad,
                sag=(
                    Hucre(
                        _yuzde(r.getiri, 1, True),
                        alt=f"giriş {r.ilk_gorulme[8:10]}.{r.ilk_gorulme[5:7]}",
                    ),
                    Hucre(
                        _tutar(r.son_hacim),
                        kalin=True,
                        vurgu=True,
                        alt=f"ilk hafta {_tutar(r.ilk_hacim)}",
                    ),
                ),
            )
            for r in satirlar
        ),
    )


def opsiyon_ciz(
    satirlar: list[OpsiyonSatiri], adlar: dict[str, str], tarih: str, taranan: int
) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Olağandışı Opsiyon Hareketi",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"Hacmi açık pozisyonun yarısını aşan ETF'ler · 45 güne kadar · {taranan} ETF",
        sutunlar=("ETF", "Hacim", "Hacim / açık"),
        satirlar=tuple(
            Satir(
                ust=r.sembol,
                etiket=r.yon,
                alt=adlar.get(r.sembol, r.sembol),
                sag=(
                    Hucre(f"{r.hacim:,}".replace(",", "."), alt=f"en aktif {r.en_aktif}"),
                    Hucre(
                        f"{_sayi(r.oran, 1)}×",
                        kalin=True,
                        vurgu=True,
                        alt=f"put/çağrı {_sayi(min(r.put_cagri, 99.0), 2)}",
                    ),
                ),
            )
            for r in satirlar
        ),
    )


def akis_ciz(girenler: list[AkisSatiri], cikanlar: list[AkisSatiri], tarih: str) -> Kart:
    def satir(r: AkisSatiri) -> Satir:
        return Satir(
            ust=r.sembol,
            alt=r.ad,
            sag=(Hucre(_tutar(r.akis), kalin=True, vurgu=True), Hucre(_yuzde(r.oran, 1, True))),
        )

    ogeler: list[Satir | Bolum] = []
    if girenler:
        ogeler += [Bolum("Para girenler"), *map(satir, girenler)]
    if cikanlar:
        ogeler += [Bolum("Para çıkanlar"), *map(satir, cikanlar)]
    return Kart(
        fikir=FIKIR,
        ad="Fon Akışı",
        tarih=_tarih(tarih),
        kaynak="Yahoo Finance (toplam varlık)",
        alt_baslik="Son 5 işlem günü · tahmini net akış, fiyat etkisi çıkarılmış",
        sutunlar=("ETF", "Akış", "Varlığa oranı"),
        satirlar=tuple(ogeler),
    )


Hisse = tuple[str, str, float, Olcum | None, bool]  # sembol, ad, ağırlık, ölçüm, 52h zirvede


def hisseler_ciz(etf: str, ad: str, hisseler: list[Hisse], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad=f"{etf} · Temanın Hisseleri",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"{ad} · en büyük {len(hisseler)} hisse",
        sutunlar=("Hisse", "Ağırlık", "1 ay", "3 ay"),
        satirlar=tuple(
            Satir(
                ust=h,
                etiket="52h zirve" if zirvede else "",
                alt=hisse_ad,
                sag=(
                    Hucre(_yuzde(agirlik, 1)),
                    _getiri(o.g1a if o else None),
                    _getiri(o.g3a if o else None, vurgu=True),
                ),
            )
            for h, hisse_ad, agirlik, o, zirvede in hisseler
        ),
    )
