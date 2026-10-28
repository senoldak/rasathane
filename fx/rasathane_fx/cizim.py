"""FX kartları (ortak Kâğıt): pano, sinyaller, risk, carry, faiz, bağlar, oynaklık, seanslar,
CFTC, karne ve kura duyarlı hisseler."""

import datetime

import pandas as pd
from rasathane_ortak import kagit
from rasathane_ortak.kagit import Bolum, Cizgi, Grafik, Hucre, Isaret, Kart, Satir

from .analiz import (
    SEANSLAR,
    UFUKLAR,
    BagOlcum,
    Beklenti,
    Carry,
    Duyarlilik,
    FaizFarki,
    Karne,
    Oynaklik,
    Risk,
)
from .evren import KURLAR, PARA_KURU
from .raporlar import Pozisyon
from .tarama import TURLER, Olcum, Sinyal, ad, kapanis

FIKIR = "FX"
KAYNAK = "Yahoo Finance"
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
    return _sayi(x, 2 if x >= 100 else 3 if x >= 10 else 4)


def _getiri(x: float | None, vurgu: bool = False, basamak: int = 1) -> Hucre:
    if x is None:
        return Hucre("—", ikincil=True)
    return Hucre(_yuzde(x, basamak, True), kalin=vurgu, vurgu=vurgu)


def _bp(x: float | None, vurgu: bool = False) -> Hucre:
    if x is None:
        return Hucre("—", ikincil=True)
    return Hucre(("+" if x >= 0 else "−") + _sayi(abs(x), 0) + " bp", kalin=vurgu, vurgu=vurgu)


def _puan(x: float, isaret: bool = False) -> str:
    on = ("+" if x >= 0 else "−") if isaret else ("−" if x < 0 else "")
    return on + _sayi(abs(x), 2)


def _tarih(iso: str) -> str:
    return str(kagit.tarih_metni(datetime.date.fromisoformat(iso)))


def etiket(sembol: str) -> str:
    """Telegram etiketi: TRY=X → #USDTRY."""
    return "#" + ad(sembol).replace("/", "").replace(" ", "_")


def _para_adi(para: str) -> str:
    k = PARA_KURU.get(para)
    return k.ad if k else para


def _olcum_satiri(o: Olcum, ust: str, alt: str = "") -> Satir:
    return Satir(
        ust=ust,
        alt=alt,
        sag=(
            Hucre(_fiyat(o.kapanis)),
            _getiri(o.gunluk, vurgu=True, basamak=2),
            _getiri(o.g1a),
            _getiri(o.gyb),
        ),
    )


def pano_ciz(olcumler: dict[str, Olcum], sepet: Olcum | None, tarih: str) -> Kart:
    ogeler: list[Satir | Bolum] = []
    grup = ""
    for k in KURLAR:
        o = olcumler.get(k.sembol)
        if o is None:
            continue
        if k.grup != grup:
            grup = k.grup
            ogeler.append(Bolum(grup))
        ogeler.append(_olcum_satiri(o, k.ad))
        if k.sembol == "GBPTRY=X" and sepet is not None:
            ogeler.append(_olcum_satiri(sepet, "TL sepeti", "USD ve EUR ortalaması"))
    return Kart(
        fikir=FIKIR,
        ad="FX Panosu",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="Günlük kapanışlar · yılbaşı getirisi geçen yılın son kapanışına göre",
        sutunlar=("Kur", "Kapanış", "Gün", "1 ay", "Yılbaşı"),
        satirlar=tuple(ogeler),
    )


_SEVIYE_SUTUNU = {
    "yukselis": "Oynaklığa göre",
    "dusus": "Oynaklığa göre",
    "zirve_52": "Önceki zirve",
    "dip_52": "Önceki dip",
    "oynaklik": "1 ay oynaklık",
}


def _seviye(s: Sinyal) -> Hucre:
    if s.tur in ("yukselis", "dusus"):
        return Hucre(f"{_sayi(abs(s.seviye), 1)}σ", kalin=True, vurgu=True)
    if s.tur == "oynaklik":
        return Hucre(_yuzde(s.seviye, 1), kalin=True, vurgu=True)
    return Hucre(_fiyat(s.seviye), kalin=True, vurgu=True)


def sinyal_listesi_ciz(tur: str, sinyaller: list[Sinyal], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad=TURLER[tur],
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"Bugün {len(sinyaller)} kur",
        sutunlar=("Kur", "Kapanış", _SEVIYE_SUTUNU[tur]),
        satirlar=tuple(
            Satir(
                ust=ad(s.sembol),
                sag=(Hucre(_fiyat(s.kapanis), alt=_yuzde(s.gunluk, 2, True)), _seviye(s)),
            )
            for s in sinyaller
        ),
    )


def _pencere(s: pd.Series) -> tuple[tuple[datetime.date, ...], tuple[float, ...]]:
    p = s.dropna().iloc[-GRAFIK_GUN:]
    return tuple(g.date() for g in p.index), tuple(float(v) for v in p)


def _cizgi(s: pd.Series, **ayar: bool) -> Cizgi:
    return Cizgi(
        tuple(
            (g.date(), float(v))
            for g, v in zip(pd.DatetimeIndex(s.index), s, strict=True)
            if pd.notna(v)
        ),
        **ayar,
    )


def sinyal_grafigi(s: Sinyal, df: pd.DataFrame, tarih: str) -> Grafik:
    tum = kapanis(df)
    gunler, seri = _pencere(tum)
    sma200 = _cizgi(tum.rolling(200).mean().iloc[-GRAFIK_GUN:])
    yataylar: tuple[tuple[float, str], ...] = ()
    if s.tur == "zirve_52":
        yataylar = ((s.seviye, "önceki zirve"),)
    elif s.tur == "dip_52":
        yataylar = ((s.seviye, "önceki dip"),)
    return Grafik(
        fikir=FIKIR,
        tarih=_tarih(tarih),
        baslik=f"{ad(s.sembol)} · {TURLER[s.tur]}",
        alt_baslik="1 yıl · çizgi SMA 200",
        ozet=(
            ("Kapanış", Hucre(_fiyat(s.kapanis), kalin=True)),
            ("Günlük", Hucre(_yuzde(s.gunluk, 2, True), kalin=True, vurgu=True)),
            (_SEVIYE_SUTUNU[s.tur], _seviye(s)),
        ),
        gunler=gunler,
        seri=seri,
        kaynak=KAYNAK,
        isaretler=(Isaret(gunler[-1], ""),),
        cizgiler=(sma200,) if len(sma200.noktalar) >= 2 else (),
        yataylar=yataylar,
    )


def risk_ciz(r: Risk, tarih: str) -> Kart:
    yon = "risk iştahı" if r.g1a >= 0 else "güvenli limana kaçış"
    satirlar: list[Satir | Bolum] = [
        Satir(
            ust="Risk skoru",
            etiket="uç" if r.yuzdelik <= 0.05 or r.yuzdelik >= 0.95 else "",
            alt=f"1 ay: {yon}",
            sag=(
                _getiri(r.gunluk, vurgu=True, basamak=2),
                Hucre("—", ikincil=True),
                _getiri(r.g1a, vurgu=True),
            ),
        ),
        Bolum("Riskli paralar"),
    ]
    for riskli in (True, False):
        if not riskli:
            satirlar.append(Bolum("Güvenli limanlar"))
        satirlar += [
            Satir(
                ust=_para_adi(s.para),
                sag=(_getiri(s.gunluk, basamak=2), _getiri(s.g1h), _getiri(s.g1a)),
            )
            for s in r.satirlar
            if s.riskli == riskli
        ]
    return Kart(
        fikir=FIKIR,
        ad="Risk Panosu",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=(
            "USD karşısında getiri · skorun 1 aylık değeri son 5 yılın "
            f"%{_sayi(r.yuzdelik * 100, 0)} yüzdeliğinde"
        ),
        sutunlar=("Para", "Gün", "1 hafta", "1 ay"),
        satirlar=tuple(satirlar),
    )


def carry_ciz(satirlar: list[Carry], abd: float, tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Carry Tablosu",
        tarih=_tarih(tarih),
        kaynak="BIS politika faizleri · Yahoo Finance",
        alt_baslik=(
            f"ABD politika faizi %{_sayi(abd, 2)} · taşıma/oynaklık: faiz farkı ÷ 3 aylık "
            "yıllık oynaklık"
        ),
        sutunlar=("Para", "Faiz", "Fark (puan)", "Taşıma/oyn.", "1 ay"),
        satirlar=tuple(
            Satir(
                ust=c.para,
                alt=f"oyn. {_yuzde(c.oynaklik, 1)}",
                sag=(
                    Hucre(f"%{_sayi(c.faiz, 2)}"),
                    Hucre(_puan(c.fark, True)),
                    Hucre(_sayi(c.oran, 2), kalin=True, vurgu=True),
                    _getiri(c.g1a),
                ),
            )
            for c in satirlar
        ),
        not_="Getiri USD karşısında; pozitifse para birimi değer kazanmış.",
    )


def faiz_karari_ciz(degisenler: list[tuple[str, float, float]], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Faiz Kararı",
        tarih=_tarih(tarih),
        kaynak="BIS politika faizleri",
        alt_baslik="BIS verisinde politika faizi değişen merkez bankaları",
        sutunlar=("Para", "Önceki", "Yeni", "Değişim"),
        satirlar=tuple(
            Satir(
                ust=_para_adi(p),
                sag=(
                    Hucre(f"%{_sayi(eski, 2)}"),
                    Hucre(f"%{_sayi(yeni, 2)}", kalin=True),
                    _bp((yeni - eski) * 100, vurgu=True),
                ),
            )
            for p, eski, yeni in degisenler
        ),
    )


def baglar_ciz(olcumler: list[BagOlcum], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Kur Bağları",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="Günlük getirilerin korelasyonu · kırılma: 60 gün ile 1 yıl arasında 0,5+ fark",
        sutunlar=("Bağ", "60 gün", "1 yıl"),
        satirlar=tuple(
            Satir(
                ust=b.bag.ad,
                etiket="kırılma" if b.kirildi else "",
                alt=b.bag.dis_ad,
                sag=(
                    Hucre(_puan(b.kisa, True), kalin=True, vurgu=b.kirildi),
                    Hucre(_puan(b.uzun, True)),
                ),
            )
            for b in olcumler
        ),
    )


def bag_grafigi(b: BagOlcum, tarih: str) -> Grafik:
    gunler, seri = tuple(g.date() for g in b.seri.index), tuple(float(v) for v in b.seri)
    return Grafik(
        fikir=FIKIR,
        tarih=_tarih(tarih),
        baslik=f"{b.bag.ad} · Korelasyon Kırılması",
        alt_baslik=f"60 günlük kayan korelasyon · {b.bag.dis_ad}",
        ozet=(
            ("60 gün", Hucre(_puan(b.kisa, True), kalin=True, vurgu=True)),
            ("1 yıl", Hucre(_puan(b.uzun, True), kalin=True)),
        ),
        gunler=gunler,
        seri=seri,
        kaynak=KAYNAK,
        isaretler=(Isaret(gunler[-1], ""),),
        yataylar=((b.uzun, "1 yıllık"), (0.0, "")),
    )


def oynaklik_ciz(satirlar: list[Oynaklik], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Kur Oynaklığı",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik="Gerçekleşen yıllık oynaklık · yüzdelik: 1 aylık değerin son 5 yıldaki yeri",
        sutunlar=("Kur", "1 ay", "3 ay", "5 yıl yüzdelik"),
        satirlar=tuple(
            Satir(
                ust=ad(o.sembol),
                etiket="uç" if o.yuzdelik >= 0.95 or o.yuzdelik <= 0.05 else "",
                sag=(
                    Hucre(_yuzde(o.ay, 1), kalin=True),
                    Hucre(_yuzde(o.ceyrek, 1)),
                    Hucre(_yuzde(o.yuzdelik, 0), vurgu=o.yuzdelik >= 0.95),
                ),
            )
            for o in satirlar
        ),
    )


def seans_ciz(seanslar: dict[str, dict[str, float]], tarih: str) -> Kart:
    adlar = tuple(a for a, _, _ in SEANSLAR)
    satirlar = []
    for s, d in seanslar.items():
        en = max(adlar, key=lambda a: d[a])
        satirlar.append(
            Satir(
                ust=ad(s),
                sag=tuple(Hucre(_yuzde(d[a], 2), kalin=a == en, vurgu=a == en) for a in adlar),
            )
        )
    return Kart(
        fikir=FIKIR,
        ad="Seanslara Göre Hareket",
        tarih=_tarih(tarih),
        kaynak="Yahoo Finance (saatlik)",
        alt_baslik="Son 5 gün · seans başına ortalama mutlak saatlik hareket toplamı",
        sutunlar=("Kur", *adlar),
        satirlar=tuple(satirlar),
        not_="Seanslar TR saatiyle: Asya 02–10, Londra 10–15, New York 15–24.",
    )


def faiz_farki_ciz(satirlar: list[FaizFarki], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Faiz Farkı ve Kur",
        tarih=_tarih(tarih),
        kaynak="FRED · ECB · Japonya Maliye Bakanlığı · Yahoo Finance",
        alt_baslik="2 yıllık devlet tahvili faiz farkı · korelasyon: 1 yıllık haftalık değişimler",
        sutunlar=("2 yıllık", "Fark (puan)", "1 ay", "Kur 1 ay", "Korelasyon"),
        satirlar=tuple(
            Satir(
                ust=f.ad,
                alt=ad(f.kur),
                sag=(
                    Hucre(_puan(f.fark, True), kalin=True),
                    _bp(None if f.fark_1a is None else f.fark_1a * 100, vurgu=True),
                    _getiri(f.kur_1a),
                    (
                        Hucre("—", ikincil=True)
                        if f.korelasyon is None
                        else Hucre(_puan(f.korelasyon, True))
                    ),
                ),
            )
            for f in satirlar
        ),
        not_="Euro faizi ECB'nin AAA euro bölgesi eğrisinden (Almanya'ya yakın).",
    )


_AYLAR = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)


def fed_ciz(beklentiler: list[Beklenti], simdiki: float, tarih: str, ad_: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad=ad_,
        tarih=_tarih(tarih),
        kaynak="CME 30 günlük Fed fonu vadelileri (Yahoo) · BIS",
        alt_baslik=f"Ay ortalaması örtük faiz · bugünkü politika faizi %{_sayi(simdiki, 3)}",
        sutunlar=("Ay", "Örtük faiz", "Bugüne göre", "Günlük"),
        satirlar=tuple(
            Satir(
                ust=f"{_AYLAR[b.ay.month - 1]} {b.ay.year}",
                sag=(
                    Hucre(f"%{_sayi(b.faiz, 3)}"),
                    _bp(b.fark, vurgu=True),
                    _bp(b.degisim),
                ),
            )
            for b in beklentiler
        ),
        not_="Eksi fark piyasanın indirim fiyatladığını gösterir; 25 bp bir adımdır.",
    )


def cot_ciz(pozisyonlar: list[Pozisyon]) -> Kart:
    def kontrat(x: int, isaret: bool = False) -> str:
        on = ("+" if x >= 0 else "−") if isaret else ("−" if x < 0 else "")
        return on + f"{abs(x):,}".replace(",", ".")

    return Kart(
        fikir=FIKIR,
        ad="Fon Pozisyonları",
        tarih=_tarih(pozisyonlar[0].donem),
        kaynak="CFTC TFF raporu",
        alt_baslik="Kaldıraçlı fonların net vadeli pozisyonu (kontrat) · yüzdelik son 3 yıla göre",
        sutunlar=("Para", "Net", "Haftalık", "3 yıl yüzdelik"),
        satirlar=tuple(
            Satir(
                ust="Dolar endeksi" if p.para == "DXY" else p.para,
                etiket="uç" if p.uc else "",
                alt=f"açık pozisyonun {_yuzde(p.net / p.acik, 0, True)}" if p.acik else "",
                sag=(
                    Hucre(kontrat(p.net)),
                    Hucre(kontrat(p.degisim, True), kalin=True, vurgu=True),
                    Hucre(_yuzde(p.yuzdelik, 0), kalin=p.uc, vurgu=p.uc),
                ),
            )
            for p in pozisyonlar
        ),
        not_="Pozitif net: fonlar para biriminin USD karşısında değer kazanmasına oynuyor.",
    )


def karne_ciz(karneler: list[Karne], tarih: str) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Sinyal Karnesi",
        tarih=_tarih(tarih),
        kaynak="FX sinyal kaydı · Yahoo Finance",
        alt_baslik="Sinyal yönünde ortalama getiri, altta isabet oranı (işlem günü sonra)",
        sutunlar=("Sinyal", *(f"{u} gün" for u in UFUKLAR)),
        satirlar=tuple(
            Satir(
                ust=TURLER[k.tur],
                alt=f"{k.sayi[UFUKLAR[0]]} sinyal",
                sag=tuple(
                    (
                        Hucre(
                            _yuzde(k.ortalama[u], 2, True),
                            kalin=True,
                            alt=f"isabet {_yuzde(k.isabet[u], 0)}",
                        )
                        if u in k.ortalama
                        else Hucre("—", ikincil=True)
                    )
                    for u in UFUKLAR
                ),
            )
            for k in karneler
        ),
    )


def duyarlilik_ciz(satirlar: list[Duyarlilik], tarih: str, adet: int = 15) -> Kart:
    def satir(d: Duyarlilik) -> Satir:
        return Satir(
            ust=d.kod,
            sag=(
                Hucre(_puan(d.beta, True), kalin=True, vurgu=True),
                Hucre(_yuzde(d.r2, 0)),
            ),
        )

    return Kart(
        fikir=FIKIR,
        ad="Kura Duyarlı Hisseler",
        tarih=_tarih(tarih),
        kaynak="Yahoo Finance · Borsa İstanbul pay bülteni",
        alt_baslik=(
            "En hacimli 100 pay · 2 yıl haftalık · USD/TRY %1 artınca hissenin BIST 100'e göre "
            "fazla getirisi"
        ),
        sutunlar=("Hisse", "Duyarlılık", "R²"),
        satirlar=(
            Bolum("Kur artışından en çok yararlananlar"),
            *(satir(d) for d in satirlar[:adet]),
            Bolum("Kur artışında en çok geride kalanlar"),
            *(satir(d) for d in reversed(satirlar[-adet:])),
        ),
    )
