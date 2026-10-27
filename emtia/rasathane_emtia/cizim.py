"""Emtia kartları (ortak Kâğıt): pano, oranlar, sinyal listeleri ve grafikleri, EIA, CFTC, takvim."""

import datetime

import pandas as pd
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Bolum, Cizgi, Grafik, Hucre, Isaret, Kart, Satir

from .evren import ADLAR, DOLAR_ENDEKSI, EMTIALAR, USDTRY
from .raporlar import Pozisyon, Stok
from .tarama import DONEM, TURLER, Olcum, OranOlcum, Sinyal

FIKIR = "Emtia"
KAYNAK = "Yahoo Finance (sürekli vadeli)"
SAYFA_SATIRI = 10
GRAFIK_GUN = 252


def _sayi(x: float, basamak: int = 2) -> str:
    s: str = f"{x:,.{basamak}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _yuzde(x: float, basamak: int = 1, isaret: bool = False) -> str:
    s = _sayi(abs(x) * 100, basamak)
    on = ("+" if x >= 0 else "−") if isaret else ""
    return f"{on}%{s}"


def _fiyat(x: float) -> str:
    return _sayi(x, 0 if x >= 1000 else 2 if x >= 10 else 3)


def _getiri(x: float | None, vurgu: bool = False) -> Hucre:
    if x is None:
        return Hucre("—", ikincil=True)
    return Hucre(_yuzde(x, 1, True), kalin=vurgu, vurgu=vurgu)


def _tarih(iso: str) -> str:
    return str(kagit.tarih_metni(datetime.date.fromisoformat(iso)))


def ad(sembol: str) -> str:
    return ADLAR[sembol].ad if sembol in ADLAR else sembol


def etiket(sembol: str) -> str:
    """Telegram etiketi: GC=F → #Altın."""
    return "#" + ad(sembol).split(" (")[0].replace(" ", "_")


def _olcum_satiri(o: Olcum, ust: str, alt: str) -> Satir:
    return Satir(
        ust=ust,
        alt=alt,
        sag=(
            Hucre(_fiyat(o.kapanis)),
            _getiri(o.gunluk, vurgu=True),
            _getiri(o.g1a),
            _getiri(o.gyb),
        ),
    )


def pano_ciz(olcumler: dict[str, Olcum], gram: Olcum | None, tarih: str) -> Kart:
    ogeler: list[Satir | Bolum] = []
    grup = ""
    for e in EMTIALAR:
        o = olcumler.get(e.sembol)
        if o is None:
            continue
        if e.grup != grup:
            grup = e.grup
            ogeler.append(Bolum(grup))
        ogeler.append(_olcum_satiri(o, e.ad, e.birim))
    kur: list[Satir | Bolum] = []
    if gram is not None:
        kur.append(_olcum_satiri(gram, "Gram altın", "TL/gram · ons × USD/TRY"))
    if USDTRY in olcumler:
        kur.append(_olcum_satiri(olcumler[USDTRY], "USD/TRY", "TL"))
    if DOLAR_ENDEKSI in olcumler:
        kur.append(_olcum_satiri(olcumler[DOLAR_ENDEKSI], "Dolar endeksi", "DXY"))
    if kur:
        ogeler += [Bolum("Türkiye ve dolar"), *kur]
    return Kart(
        fikir=FIKIR,
        ad="Emtia Panosu",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="Ön ay vadeli kapanışları · yılbaşı getirisi geçen yılın son kapanışına göre",
        sutunlar=("Emtia", "Fiyat", "Gün", "1 ay", "Yılbaşı"),
        satirlar=tuple(ogeler),
    )


def oranlar_ciz(satirlar: list[OranOlcum], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Emtia Oranları",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="5 yıllık yüzdelik: oranın son 5 yılda bugünkünden düşük kaldığı günlerin payı",
        sutunlar=("Oran", "Değer", "1 ay", "5 yıl yüzdelik"),
        satirlar=tuple(
            Satir(
                ust=r.oran.ad,
                etiket="uç" if r.uc else "",
                alt=r.oran.anlam,
                sag=(
                    Hucre(_sayi(r.deger, 2 if r.deger >= 1 else 4)),
                    _getiri(r.g1a),
                    Hucre(_yuzde(r.yuzdelik, 0), kalin=True, vurgu=r.uc),
                ),
            )
            for r in satirlar
        ),
    )


_SEVIYE_SUTUNU = {
    "yukselis": "Oynaklığa göre",
    "dusus": "Oynaklığa göre",
    "zirve_52": "Önceki zirve",
    "dip_52": "Önceki dip",
}


def _seviye(s: Sinyal) -> Hucre:
    if s.tur in ("yukselis", "dusus"):
        return Hucre(f"{_sayi(abs(s.seviye), 1)}σ", kalin=True, vurgu=True)
    return Hucre(_fiyat(s.seviye), kalin=True, vurgu=True)


def sinyal_listesi_ciz(tur: str, sinyaller: list[Sinyal], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad=TURLER[tur],
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"Bugün {len(sinyaller)} emtia",
        sutunlar=("Emtia", "Kapanış", _SEVIYE_SUTUNU[tur]),
        satirlar=tuple(
            Satir(
                ust=ad(s.sembol),
                alt=ADLAR[s.sembol].birim if s.sembol in ADLAR else "",
                sag=(Hucre(_fiyat(s.kapanis), alt=_yuzde(s.gunluk, 2, True)), _seviye(s)),
            )
            for s in sinyaller
        ),
    )


def _pencere(s: pd.Series) -> tuple[tuple[datetime.date, ...], tuple[float, ...]]:
    p = s.dropna().iloc[-GRAFIK_GUN:]
    return tuple(g.date() for g in p.index), tuple(float(v) for v in p)


def sinyal_grafigi(s: Sinyal, df: pd.DataFrame, tarih: str) -> Grafik:
    tum = df["Close"].astype(float).dropna()
    gunler, seri = _pencere(tum)
    sma200 = tum.rolling(200).mean().iloc[-GRAFIK_GUN:]
    cizgiler = tuple(
        c
        for c in (
            Cizgi(
                tuple(
                    (g.date(), float(v))
                    for g, v in zip(pd.DatetimeIndex(sma200.index), sma200, strict=True)
                    if pd.notna(v)
                )
            ),
        )
        if len(c.noktalar) >= 2
    )
    yataylar: tuple[tuple[float, str], ...] = ()
    if s.tur == "zirve_52":
        yataylar = ((s.seviye, "önceki zirve"),)
    elif s.tur == "dip_52":
        yataylar = ((s.seviye, "önceki dip"),)
    ozet: list[tuple[str, Hucre]] = [
        ("Kapanış", Hucre(_fiyat(s.kapanis), kalin=True)),
        ("Günlük", Hucre(_yuzde(s.gunluk, 2, True), kalin=True, vurgu=True)),
        (_SEVIYE_SUTUNU[s.tur], _seviye(s)),
    ]
    e = ADLAR.get(s.sembol)
    return Grafik(
        fikir=FIKIR,
        tarih=_tarih(tarih),
        baslik=f"{ad(s.sembol)} · {TURLER[s.tur]}",
        alt_baslik=f"{e.birim if e else s.sembol} · 1 yıl · çizgi SMA 200",
        ozet=tuple(ozet),
        gunler=gunler,
        seri=seri,
        kaynak=KAYNAK,
        isaretler=(Isaret(gunler[-1], ""),),
        cizgiler=cizgiler,
        yataylar=yataylar,
    )


def oran_grafigi(r: OranOlcum, tarih: str) -> Grafik:
    s = r.seri.dropna().iloc[-DONEM * 5 :]
    gunler, seri = tuple(g.date() for g in s.index), tuple(float(v) for v in s)
    medyan = float(r.seri.median())
    yon = "son 5 yılın en yüksek dilimi" if r.yuzdelik >= 0.5 else "son 5 yılın en düşük dilimi"
    return Grafik(
        fikir=FIKIR,
        tarih=_tarih(tarih),
        baslik=f"{r.oran.ad} · Uç Seviye",
        alt_baslik=f"{yon} · {r.oran.anlam}",
        ozet=(
            ("Oran", Hucre(_sayi(r.deger, 2 if r.deger >= 1 else 4), kalin=True)),
            ("5 yıl yüzdelik", Hucre(_yuzde(r.yuzdelik, 0), kalin=True, vurgu=True)),
            ("1 ay", _getiri(r.g1a)),
        ),
        gunler=gunler,
        seri=seri,
        kaynak=KAYNAK,
        isaretler=(Isaret(gunler[-1], ""),),
        yataylar=((medyan, "5 yıl ortanca"),),
    )


def gram_grafigi(gram: pd.Series, tarih: str) -> Grafik:
    gunler, seri = _pencere(gram)
    son, once = seri[-1], seri[-2]
    return Grafik(
        fikir=FIKIR,
        tarih=_tarih(tarih),
        baslik="Gram Altın · Yeni Zirve",
        alt_baslik="TL/gram · ons altın × USD/TRY · 5 yıllık verinin en yükseği",
        ozet=(
            ("Gram altın", Hucre(f"{_sayi(son, 0)} TL", kalin=True)),
            ("Günlük", Hucre(_yuzde(son / once - 1, 2, True), kalin=True, vurgu=True)),
        ),
        gunler=gunler,
        seri=seri,
        kaynak="Yahoo Finance (GC=F, TRY=X)",
        isaretler=(Isaret(gunler[-1], ""),),
    )


def _milyon(x: float, birim: str) -> str:
    return f"{_sayi(x, 1)} {birim}"


def stok_ciz(ad_: str, stoklar: list[Stok]) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad=ad_,
        tarih=_tarih(stoklar[0].donem),
        kaynak="EIA (ABD Enerji Bilgi İdaresi)",
        alt_baslik=f"{_tarih(stoklar[0].donem)} haftası · ABD stokları",
        sutunlar=("Kalem", "Stok", "Haftalık", "1 yıl önce"),
        satirlar=tuple(
            Satir(
                ust=s.seri.ad,
                alt=s.seri.birim,
                sag=(
                    Hucre(_milyon(s.deger, "")),
                    Hucre(
                        ("+" if s.degisim >= 0 else "−") + _sayi(abs(s.degisim), 1),
                        kalin=True,
                        vurgu=True,
                    ),
                    (
                        Hucre("—", ikincil=True)
                        if s.yil_once is None
                        else _getiri(s.deger / s.yil_once - 1)
                    ),
                ),
            )
            for s in stoklar
        ),
    )


def _kontrat(x: int, isaret: bool = False) -> str:
    on = ("+" if x >= 0 else "−") if isaret else ("−" if x < 0 else "")
    return on + f"{abs(x):,}".replace(",", ".")


def cot_ciz(pozisyonlar: list[Pozisyon]) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Fon Pozisyonları",
        tarih=_tarih(pozisyonlar[0].donem),
        kaynak="CFTC COT raporu",
        alt_baslik="Managed money net pozisyonu (kontrat) · yüzdelik son 3 yıla göre",
        sutunlar=("Emtia", "Net", "Haftalık", "3 yıl yüzdelik"),
        satirlar=tuple(
            Satir(
                ust=ad(p.sembol),
                etiket="uç" if p.uc else "",
                alt=f"açık pozisyonun {_yuzde(p.net / p.acik, 0, True)}" if p.acik else "",
                sag=(
                    Hucre(_kontrat(p.net)),
                    Hucre(_kontrat(p.degisim, True), kalin=True, vurgu=True),
                    Hucre(_yuzde(p.yuzdelik, 0), kalin=p.uc, vurgu=p.uc),
                ),
            )
            for p in pozisyonlar
        ),
    )


TAKVIM: tuple[tuple[int, str, str, str], ...] = (
    (2, "Çarşamba 17:30", "EIA petrol stokları", "Ham petrol, benzin, distilat, Cushing"),
    (3, "Perşembe 17:30", "EIA doğalgaz depoları", "ABD çalışma gazı"),
    (4, "Cuma 22:30", "CFTC pozisyon raporu", "Fonların net pozisyonu (Salı itibarıyla)"),
)


def takvim_ciz(tarih: str) -> Kart:
    """Haftanın ilk işlem günü: bu hafta hangi gün hangi kartın geleceği (TR saati, yaklaşık)."""
    bas = datetime.date.fromisoformat(tarih)
    pzt = bas - datetime.timedelta(days=bas.weekday())
    return Kart(
        fikir=FIKIR,
        ad="Haftanın Veri Takvimi",
        tarih=_tarih(tarih),
        kaynak="EIA · CFTC",
        alt_baslik="Yayın saatleri Türkiye saatiyle; kartlar akşam emtia koşusunda gelir",
        sutunlar=("Rapor", "Gün"),
        satirlar=tuple(
            Satir(
                ust=rapor,
                alt=aciklama,
                sag=(
                    Hucre(
                        kagit.tarih_metni(pzt + datetime.timedelta(days=gun)),
                        alt=saat.split()[1],
                    ),
                ),
            )
            for gun, saat, rapor, aciklama in TAKVIM
        ),
        not_="Saatler ABD yaz/kış saatine göre bir saat kayabilir; tatil haftalarında EIA bir gün gecikir.",
    )
