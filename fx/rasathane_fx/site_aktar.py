"""Site verisi: fx günlük akışından `site-veri/fx/` altında sayfa ve seri JSON dosyaları.

Analizler (carry, risk, faiz farkı, Fed, bağlar, oynaklık, seanslar, CFTC, geçmiş isabet, kura
duyarlı hisseler) kartlarla aynı fonksiyonlardan üretilir; kartlara girmeyen veriler de siteye
yazılır. Sayfa metinlerinde yön dili kullanılmaz: geçmiş sonuç betimlenir, öneri verilmez.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz, seri_cok_yaz, seri_yaz

from . import analiz, raporlar
from .evren import BAGLAR, KURLAR, PARA_KURU, SEPET
from .tarama import TURLER, Olcum, Sinyal, ad, kapanis, sepet

BOLUM = "fx"
SERI_GUN = 252
HAFTA_SAYI = 104
GECMIS_GUN = 90
UYARI = "Yatırım tavsiyesi değildir. Veriler gecikmelidir."
_YAHOO = Kaynak("Yahoo Finance", "https://finance.yahoo.com/")
_BIS = Kaynak("BIS", "https://www.bis.org/statistics/cbpol.htm")
_FRED = Kaynak("FRED", "https://fred.stlouisfed.org/")
_ECB = Kaynak("ECB", "https://www.ecb.europa.eu/")
_MOF = Kaynak("Japonya Maliye Bakanlığı", "https://www.mof.go.jp/english/")
_CFTC = Kaynak("CFTC", "https://www.cftc.gov/")
_BIST = Kaynak("Borsa İstanbul", "https://www.borsaistanbul.com/")
_GRUP_SEPET = "Türk lirası"
_UFUKLAR = (5, 20, 60)


def _sayfa(
    kok: Path,
    sayfa: str,
    simdi: datetime.datetime,
    *,
    baslik: str,
    aciklama: str,
    kaynaklar: list[Kaynak],
    sutunlar: list[Sutun],
    satirlar: list[dict[str, object]],
    suzgecler: tuple[str, ...] = (),
) -> Path:
    return Path(
        sayfa_yaz(
            kok,
            BOLUM,
            sayfa,
            baslik=baslik,
            aciklama=f"{aciklama} {UYARI}",
            guncellendi=simdi,
            kaynaklar=kaynaklar,
            sutunlar=sutunlar,
            satirlar=satirlar,
            suzgecler=suzgecler,
        )
    )


def _gun(i: Any) -> datetime.date:
    gun: datetime.date = pd.Timestamp(i).date()
    return gun


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
    birim: str,
    kapanis_: pd.Series,
    isaretler: list[tuple[datetime.date, str]],
) -> None:
    """Ortak gösterge seti: EMA 144/233/377 ve RSI (14). Göstergeler tam geçmiş üzerinde hesaplanır."""
    c = kapanis_.astype(float).dropna()
    gunluk = pd.DataFrame(
        {
            "kapanis": c,
            "ema144": c.ewm(span=144, adjust=False).mean(),
            "ema233": c.ewm(span=233, adjust=False).mean(),
            "ema377": c.ewm(span=377, adjust=False).mean(),
            "rsi14": _rsi(c),
        }
    )
    t, s = _sec(gunluk, SERI_GUN)
    seri_cok_yaz(kok, BOLUM, anahtar, t, s, ad=ad(anahtar), birim=birim, isaretler=isaretler)

    h = c.resample("W-FRI").last().dropna()
    haftalik = pd.DataFrame(
        {
            "kapanis": h,
            "ema144": h.ewm(span=144, adjust=False).mean(),
            "ema233": h.ewm(span=233, adjust=False).mean(),
            "rsi14": _rsi(h),
        }
    )
    t, s = _sec(haftalik, HAFTA_SAYI)
    seri_cok_yaz(
        kok, BOLUM, f"{anahtar}-hafta", t, s, ad=ad(anahtar), birim=birim, isaretler=isaretler
    )


def _olcum_satiri(sembol: str, grup: str, o: Olcum) -> dict[str, object]:
    return {
        "ad": ad(sembol),
        "grup": grup,
        "kapanis": o.kapanis,
        "gunluk": o.gunluk,
        "g1h": o.g1h,
        "g1a": o.g1a,
        "gyb": o.gyb,
        "seri": sembol,
    }


def _hareketler(
    tablolar: dict[str, pd.DataFrame],
    bulunan: list[Sinyal],
    kayit: list[dict[str, str]],
    gunler: list[str],
) -> list[dict[str, object]]:
    """Son GECMIS_GUN işlem gününün hareketleri: sinyal kaydı ve bugünkü hareketler birleşir.

    Aynı gün ve paritedeki birden çok hareket tek satırda, türleri "·" ile ayrılmış olur.
    """
    sinir = gunler[-GECMIS_GUN] if len(gunler) > GECMIS_GUN else (gunler[0] if gunler else "")
    kayit_gunleri = [r for r in kayit if sinir <= r["tarih"]]
    kayitlar: dict[tuple[str, str], dict[str, object]] = {}
    bag_adlari = {b.anahtar: b.ad for b in BAGLAR}

    def ekle(gun: str, sembol: str, tur_ad: str, c: float | None, g: float | None) -> None:
        anahtar = (gun, sembol)
        if anahtar in kayitlar:
            kayitlar[anahtar]["tur"] = f"{kayitlar[anahtar]['tur']} · {tur_ad}"
            return
        kayitlar[anahtar] = {
            "tarih": gun,
            "ad": bag_adlari[sembol] if sembol in bag_adlari else ad(sembol),
            "tur": tur_ad,
            "kapanis": c,
            "gunluk": g,
            "seri": None if sembol in bag_adlari else sembol,
        }

    for r in kayit_gunleri:
        sembol, tur = r["sembol"], r["tur"]
        if tur == "bag":
            ekle(r["tarih"], sembol, "Kur bağı kırılması", None, None)
            continue
        if sembol not in tablolar:
            continue
        c = kapanis(tablolar[sembol])
        yer = int(c.index.searchsorted(pd.Timestamp(r["tarih"])))
        if yer >= len(c) or c.index[yer].date().isoformat() != r["tarih"] or yer == 0:
            continue
        g = float(c.iloc[yer] / c.iloc[yer - 1] - 1)
        ekle(r["tarih"], sembol, TURLER.get(tur, tur), float(c.iloc[yer]), g)

    gun_bugun = gunler[-1] if gunler else ""
    for sy in bulunan:
        ekle(gun_bugun, sy.sembol, TURLER[sy.tur], sy.kapanis, sy.gunluk)

    return sorted(kayitlar.values(), key=lambda r: (str(r["tarih"]), str(r["ad"])), reverse=True)


def _pano(
    kok: Path,
    simdi: datetime.datetime,
    olcumler: dict[str, Olcum],
    tablolar: dict[str, pd.DataFrame],
    isaret: dict[str, list[tuple[datetime.date, str]]],
) -> Path:
    satirlar: list[dict[str, object]] = []
    for k in KURLAR:
        if k.sembol not in olcumler or k.sembol not in tablolar:
            continue
        satirlar.append(_olcum_satiri(k.sembol, k.grup, olcumler[k.sembol]))
    if SEPET in olcumler:
        satirlar.append(_olcum_satiri(SEPET, _GRUP_SEPET, olcumler[SEPET]))
    for s in satirlar:
        _fiyat_serisi(
            kok,
            str(s["seri"]),
            "",
            kapanis(tablolar[str(s["seri"])]) if s["seri"] != SEPET else _sepet_serisi(tablolar),
            isaret.get(str(s["seri"]), []),
        )
    return _sayfa(
        kok,
        "pano",
        simdi,
        baslik="FX panosu",
        aciklama="Majör, çapraz, Avrupa, gelişen ülke ve TL kurları ile dolar endeksi. "
        "Her biri için günlük, 1 aylık ve yılbaşından beri getiri.",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Parite", "metin"),
            Sutun("grup", "Grup", "metin"),
            Sutun("kapanis", "Kapanış", "sayi", 4),
            Sutun("gunluk", "Günlük", "yuzde", 2),
            Sutun("g1h", "1 hafta", "yuzde", 2),
            Sutun("g1a", "1 ay", "yuzde", 2),
            Sutun("gyb", "Yılbaşından beri", "yuzde", 2),
        ],
        satirlar=satirlar,
        suzgecler=("grup",),
    )


def _sepet_serisi(tablolar: dict[str, pd.DataFrame]) -> pd.Series:
    sp = sepet(tablolar)
    if sp is None:
        return pd.Series(dtype=float)
    return kapanis(sp)


def _risk(kok: Path, simdi: datetime.datetime, tablolar: dict[str, pd.DataFrame]) -> Path | None:
    r = analiz.risk(tablolar)
    if r is None:
        return None
    satirlar: list[dict[str, object]] = [
        {
            "ad": PARA_KURU[s.para].ad if s.para in PARA_KURU else s.para,
            "grup": "Riskli para" if s.riskli else "Güvenli liman",
            "gunluk": s.gunluk,
            "g1h": s.g1h,
            "g1a": s.g1a,
        }
        for s in r.satirlar
    ]
    satirlar.append(
        {
            "ad": "Risk skoru (riskli − güvenli)",
            "grup": "Skor",
            "gunluk": r.gunluk,
            "g1a": r.g1a,
            "yuzdelik": r.yuzdelik,
            "seri": "risk-skor",
        }
    )
    noktalar = [(_gun(i), float(v)) for i, v in r.skor.dropna().iloc[-SERI_GUN:].items()]
    seri_yaz(kok, BOLUM, "risk-skor", noktalar, ad="Risk skoru (birikimli)", birim="oran")
    return _sayfa(
        kok,
        "risk",
        simdi,
        baslik="Risk iştahı",
        aciklama="Riskli paraların (AUD, NZD, MXN, ZAR, BRL) ile güvenli limanların (JPY, CHF) "
        "USD karşısındaki getirisi. Skor iki grubun farkıdır; yüzdelik, son 5 yıldaki 1 aylık "
        "farkın dilimidir.",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Kalem", "metin"),
            Sutun("grup", "Grup", "metin"),
            Sutun("gunluk", "Günlük", "yuzde", 2),
            Sutun("g1h", "1 hafta", "yuzde", 2),
            Sutun("g1a", "1 ay", "yuzde", 2),
            Sutun("yuzdelik", "5 yıllık dilim", "yuzde", 0),
        ],
        satirlar=satirlar,
    )


def _politika(kok: Path, simdi: datetime.datetime, faizler: dict[str, float]) -> Path | None:
    if not faizler:
        return None
    satirlar: list[dict[str, object]] = [{"ad": p, "faiz": f} for p, f in sorted(faizler.items())]
    return _sayfa(
        kok,
        "politika",
        simdi,
        baslik="Politika faizleri",
        aciklama="BIS verisinde her para biriminin merkez bankasının son politika faizi.",
        kaynaklar=[_BIS],
        sutunlar=[
            Sutun("ad", "Para birimi", "metin"),
            Sutun("faiz", "Politika faizi (%)", "sayi", 2),
        ],
        satirlar=satirlar,
    )


def _carry(
    kok: Path,
    simdi: datetime.datetime,
    faizler: dict[str, float],
    tablolar: dict[str, pd.DataFrame],
) -> Path | None:
    cs = analiz.carry(faizler, tablolar)
    if not cs:
        return None
    satirlar: list[dict[str, object]] = [
        {
            "ad": c.para,
            "faiz": c.faiz,
            "fark": c.fark,
            "oynaklik": c.oynaklik,
            "oran": c.oran,
            "g1a": c.g1a,
        }
        for c in cs
    ]
    return _sayfa(
        kok,
        "carry",
        simdi,
        baslik="Carry tablosu",
        aciklama="Politika faizi, ABD'ye fark, 3 aylık yıllık oynaklık ve fark/oynaklık oranı. "
        "Tablo ABD faizine göre sıralanmıştır.",
        kaynaklar=[_BIS, _YAHOO],
        sutunlar=[
            Sutun("ad", "Para birimi", "metin"),
            Sutun("faiz", "Politika faizi (%)", "sayi", 2),
            Sutun("fark", "ABD'ye fark (puan)", "sayi", 2),
            Sutun("oynaklik", "3 aylık oynaklık", "yuzde", 1),
            Sutun("oran", "Fark / oynaklık", "sayi", 2),
            Sutun("g1a", "USD karşısında 1 ay", "yuzde", 1),
        ],
        satirlar=satirlar,
    )


def _faiz_farki(
    kok: Path,
    simdi: datetime.datetime,
    tahvil: dict[str, pd.Series],
    tablolar: dict[str, pd.DataFrame],
) -> Path | None:
    farklar = [
        f
        for f in (
            analiz.faiz_farki("ABD – Euro", "EURUSD=X", tahvil["ABD"], tahvil["EUR"], tablolar),
            analiz.faiz_farki("ABD – Japonya", "JPY=X", tahvil["ABD"], tahvil["JPY"], tablolar),
        )
        if f is not None
    ]
    if not farklar:
        return None
    satirlar: list[dict[str, object]] = [
        {
            "ad": f.ad,
            "kur": ad(f.kur),
            "fark": f.fark,
            "fark_1a": f.fark_1a,
            "kur_1a": f.kur_1a,
            "korelasyon": f.korelasyon,
        }
        for f in farklar
    ]
    return _sayfa(
        kok,
        "faiz-farki",
        simdi,
        baslik="Faiz farkı ve kur",
        aciklama="ABD ile Euro bölgesi ve Japonya arasındaki 2 yıllık devlet tahvili faiz farkı; "
        "fark, bir aylık değişim ve kurla 1 yıllık korelasyon (haftalık değişimler).",
        kaynaklar=[_FRED, _ECB, _MOF, _YAHOO],
        sutunlar=[
            Sutun("ad", "Fark", "metin"),
            Sutun("kur", "Kur", "metin"),
            Sutun("fark", "Fark (puan)", "sayi", 2),
            Sutun("fark_1a", "1 ayda değişim (puan)", "sayi", 2),
            Sutun("kur_1a", "Kur 1 ay", "yuzde", 2),
            Sutun("korelasyon", "1 yıllık korelasyon", "sayi", 2),
        ],
        satirlar=satirlar,
    )


def _fed(
    kok: Path,
    simdi: datetime.datetime,
    tarih: datetime.date,
    abd: float,
    tablolar: dict[str, pd.DataFrame],
) -> Path | None:
    beklentiler = analiz.fed_beklentisi(tablolar, tarih, abd)
    if not beklentiler:
        return None
    satirlar: list[dict[str, object]] = [
        {"ad": b.ay.isoformat(), "faiz": b.faiz, "fark": b.fark, "degisim": b.degisim}
        for b in beklentiler
    ]
    return _sayfa(
        kok,
        "fed",
        simdi,
        baslik="Fed beklentisi",
        aciklama="Önümüzdeki 10 ayın 30 gün vadeli Fed fonu fiyatlarından örtük ortalama faiz; "
        "bugünkü faize göre fark ve bir önceki kapanışa göre değişim (baz puan).",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Vade ayı", "tarih"),
            Sutun("faiz", "Örtük faiz (%)", "sayi", 3),
            Sutun("fark", "Bugünkü faize göre (bp)", "sayi", 1),
            Sutun("degisim", "Bir önceki kapanışa göre (bp)", "sayi", 1),
        ],
        satirlar=satirlar,
    )


def _baglar(kok: Path, simdi: datetime.datetime, tablolar: dict[str, pd.DataFrame]) -> Path | None:
    olcumler = analiz.baglar(tablolar)
    if not olcumler:
        return None
    satirlar: list[dict[str, object]] = []
    for b in olcumler:
        anahtar = f"bag-{b.bag.anahtar}"
        seri_yaz(
            kok,
            BOLUM,
            anahtar,
            [(_gun(i), float(v)) for i, v in b.seri.items()],
            ad=f"{b.bag.ad}: 60 günlük korelasyon",
            birim="korelasyon",
        )
        satirlar.append(
            {
                "ad": b.bag.ad,
                "kisa": b.kisa,
                "uzun": b.uzun,
                "durum": "Kırıldı" if b.kirildi else "Normal",
                "seri": anahtar,
            }
        )
    return _sayfa(
        kok,
        "baglar",
        simdi,
        baslik="Kur bağları",
        aciklama="Kur ile emtia ya da faiz arasındaki 60 günlük korelasyon ve 1 yıllık korelasyon. "
        "İkisi 0,5 ya da daha fazla ayrılırsa bağ kırılmış sayılır.",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Bağ", "metin"),
            Sutun("kisa", "60 gün", "sayi", 2),
            Sutun("uzun", "1 yıl", "sayi", 2),
            Sutun("durum", "Durum", "metin"),
        ],
        satirlar=satirlar,
    )


def _oynaklik(
    kok: Path, simdi: datetime.datetime, tablolar: dict[str, pd.DataFrame]
) -> Path | None:
    oyn = analiz.oynakliklar(tablolar, [k.sembol for k in KURLAR])
    if not oyn:
        return None
    satirlar: list[dict[str, object]] = [
        {
            "ad": ad(o.sembol),
            "ay": o.ay,
            "ceyrek": o.ceyrek,
            "yuzdelik": o.yuzdelik,
            "seri": o.sembol,
        }
        for o in oyn
    ]
    return _sayfa(
        kok,
        "oynaklik",
        simdi,
        baslik="Kur oynaklığı",
        aciklama="Yıllıklaştırılmış 1 aylık ve 3 aylık oynaklık; 1 aylık oynaklığın son 5 yıldaki "
        "yüzdeliği. Tablo yüzdeliğe göre sıralanmıştır.",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Parite", "metin"),
            Sutun("ay", "1 aylık oynaklık", "yuzde", 1),
            Sutun("ceyrek", "3 aylık oynaklık", "yuzde", 1),
            Sutun("yuzdelik", "5 yıllık dilim", "yuzde", 0),
        ],
        satirlar=satirlar,
    )


def _seanslar(
    kok: Path, simdi: datetime.datetime, saatlik: dict[str, pd.DataFrame] | None
) -> Path | None:
    if not saatlik:
        return None
    olculer = analiz.seanslar(saatlik)
    if not olculer:
        return None
    satirlar: list[dict[str, object]] = [
        {
            "ad": ad(s),
            "asya": v.get("Asya"),
            "londra": v.get("Londra"),
            "new_york": v.get("New York"),
        }
        for s, v in olculer.items()
    ]
    return _sayfa(
        kok,
        "seanslar",
        simdi,
        baslik="Seanslara göre hareket",
        aciklama="Son 5 işlem gününde seans başına ortalama saatlik mutlak hareket (oran). "
        "Asya 23–07, Londra 07–12, New York 12–21 UTC.",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Parite", "metin"),
            Sutun("asya", "Asya", "yuzde", 2),
            Sutun("londra", "Londra", "yuzde", 2),
            Sutun("new_york", "New York", "yuzde", 2),
        ],
        satirlar=satirlar,
    )


def _cot(kok: Path, simdi: datetime.datetime, pozisyonlar: list[raporlar.Pozisyon]) -> Path | None:
    if not pozisyonlar:
        return None
    satirlar: list[dict[str, object]] = [
        {
            "ad": "Dolar endeksi" if p.para == "DXY" else p.para,
            "donem": p.donem,
            "net": p.net,
            "degisim": p.degisim,
            "yuzdelik": p.yuzdelik,
            "acik": p.acik,
            "uc": "Uç değer" if p.uc else "",
        }
        for p in pozisyonlar
    ]
    return _sayfa(
        kok,
        "fonlar",
        simdi,
        baslik="Fon pozisyonları",
        aciklama="CFTC TFF raporunda kaldıraçlı fonların net vadeli pozisyonu ve son 3 yıldaki dilimi.",
        kaynaklar=[_CFTC],
        sutunlar=[
            Sutun("ad", "Para birimi", "metin"),
            Sutun("donem", "Rapor tarihi", "tarih"),
            Sutun("net", "Net pozisyon", "sayi", 0),
            Sutun("degisim", "Haftalık değişim", "sayi", 0),
            Sutun("yuzdelik", "3 yıllık dilim", "yuzde", 0),
            Sutun("acik", "Açık pozisyon", "sayi", 0),
            Sutun("uc", "Durum", "metin"),
        ],
        satirlar=satirlar,
    )


def _gecmis_isabet(
    kok: Path,
    simdi: datetime.datetime,
    kayit: list[dict[str, str]],
    tablolar: dict[str, pd.DataFrame],
) -> Path | None:
    karneler = analiz.karne(kayit, tablolar)
    if not karneler:
        return None
    satirlar: list[dict[str, object]] = []
    for k in karneler:
        for u in _UFUKLAR:
            if u not in k.sayi:
                continue
            satirlar.append(
                {
                    "ad": TURLER[k.tur],
                    "ufuk": f"{u} işlem günü",
                    "sayi": k.sayi[u],
                    "ortalama": k.ortalama.get(u),
                    "isabet": k.isabet.get(u),
                }
            )
    return _sayfa(
        kok,
        "gecmis-isabet",
        simdi,
        baslik="Geçmiş isabet",
        aciklama="Kayıtlı geçmiş hareketlerden sonraki 5, 20 ve 60 işlem gününde, hareket yönünde "
        "kalan ortalama getiri ve yönünü koruyan oran. Bu bir geçmiş sonuç tablosudur; gelecek "
        "için bir şey söylemez.",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("ad", "Hareket türü", "metin"),
            Sutun("ufuk", "Ufuk", "metin"),
            Sutun("sayi", "Örnek", "sayi", 0),
            Sutun("ortalama", "Yönlü ortalama getiri", "yuzde", 2),
            Sutun("isabet", "Yönünü koruyan oran", "yuzde", 0),
        ],
        satirlar=satirlar,
        suzgecler=("ad",),
    )


def _duyarlilik(
    kok: Path, simdi: datetime.datetime, duyarlilik: list[analiz.Duyarlilik] | None
) -> Path | None:
    if not duyarlilik:
        return None
    satirlar: list[dict[str, object]] = [
        {"ad": d.kod, "beta": d.beta, "r2": d.r2} for d in duyarlilik
    ]
    return _sayfa(
        kok,
        "duyarlilik",
        simdi,
        baslik="Kura duyarlı hisseler",
        aciklama="En hacimli 100 BIST payında, hissenin BIST 100'e göre fazla haftalık getirisinin "
        "USD/TRY haftalık getirisine eğimi (2 yıllık veri). Eğim (β) ve açıklama gücü (R²).",
        kaynaklar=[_BIST, _YAHOO],
        sutunlar=[
            Sutun("ad", "Hisse", "metin"),
            Sutun("beta", "Eğim (β)", "sayi", 2),
            Sutun("r2", "R²", "sayi", 2),
        ],
        satirlar=satirlar,
    )


def _hareket_sayfasi(
    kok: Path, simdi: datetime.datetime, satirlar: list[dict[str, object]]
) -> Path:
    return _sayfa(
        kok,
        "hareketler",
        simdi,
        baslik="Hareketler",
        aciklama="Son 90 işlem gününde sert hareket, 52 hafta zirve ya da dibi, oynaklık sıçraması "
        "ve kur bağı kırılmaları. Grafiği olan satırlar seriye bağlıdır.",
        kaynaklar=[_YAHOO],
        sutunlar=[
            Sutun("tarih", "Tarih", "tarih"),
            Sutun("ad", "Parite", "metin"),
            Sutun("tur", "Hareket", "metin"),
            Sutun("kapanis", "Kapanış", "sayi", 4),
            Sutun("gunluk", "Günlük", "yuzde", 2),
        ],
        satirlar=satirlar,
    )


def aktar(
    kok: Path,
    simdi: datetime.datetime,
    tarih: str,
    tablolar: dict[str, pd.DataFrame],
    olcumler: dict[str, Olcum],
    bulunan: list[Sinyal],
    gunler: list[str],
    kayit: list[dict[str, str]],
    faizler: dict[str, float],
    tahvil: dict[str, pd.Series] | None,
    pozisyonlar: list[raporlar.Pozisyon],
    saatlik: dict[str, pd.DataFrame] | None,
    duyarlilik: list[analiz.Duyarlilik] | None,
) -> list[Path]:
    """`kok / "fx"` altına sayfaları ve serileri yazar; yazılan sayfa yollarını döndürür.

    Dış kaynaklardan gelmeyen (None) veriler için sayfa yazılmaz; önceki dosya kalır.
    """
    tarih_gun = datetime.date.fromisoformat(tarih)
    hareketler = _hareketler(tablolar, bulunan, kayit, gunler)
    isaret: dict[str, list[tuple[datetime.date, str]]] = {}
    for r in hareketler:
        if r["seri"] is not None:
            isaret.setdefault(str(r["seri"]), []).append(
                (datetime.date.fromisoformat(str(r["tarih"])), str(r["tur"]))
            )
    yollar = [
        _pano(kok, simdi, olcumler, tablolar, isaret),
        _hareket_sayfasi(kok, simdi, hareketler),
    ]
    abd = faizler.get("USD")
    for yol in (
        _risk(kok, simdi, tablolar),
        _politika(kok, simdi, faizler),
        _carry(kok, simdi, faizler, tablolar) if abd is not None else None,
        _faiz_farki(kok, simdi, tahvil, tablolar) if tahvil else None,
        _fed(kok, simdi, tarih_gun, abd, tablolar) if abd is not None else None,
        _baglar(kok, simdi, tablolar),
        _oynaklik(kok, simdi, tablolar),
        _seanslar(kok, simdi, saatlik),
        _cot(kok, simdi, pozisyonlar),
        _gecmis_isabet(kok, simdi, kayit, tablolar),
        _duyarlilik(kok, simdi, duyarlilik),
    ):
        if yol is not None:
            yollar.append(yol)
    return yollar
