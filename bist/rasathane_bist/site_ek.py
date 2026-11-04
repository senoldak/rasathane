"""VİOP ek sayfaları: açık pozisyon, put/call oranı, vade takvimi, vade eğrisi, varant.

Geçmiş seriler `gecmis.py` birikiminden gelir; her seri `seri/<anahtar>.json` olarak yazılır ve
sayfadaki satıra tıklanınca grafik çizilir. Oranlar yalnız sayı olarak yazılır, yorum eklenmez.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path

from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz, seri_cok_yaz, seri_yaz

from .bulten import PaySatiri
from .gecmis import Gecmis, gunler
from .opsiyon import bs_delta, etkin_kaldirac, ortuk_oynaklik
from .varant_adi import VARANT_TIPLERI, varant_adi_coz
from .viop import ViopSatiri, dayanak_kanonik, vadeli_mi

BOLUM = "viop"
_BIST = Kaynak("Borsa İstanbul", "https://borsaistanbul.com/")
_TUR = {"C": "Alım", "P": "Satım"}

Dayanaklar = dict[str, dict[str, float]]


def _anahtar(ad: str) -> str:
    """Seri dosya adı: yalnız küçük harf ve rakam (`ONS GUMUS` -> `ons-gumus`)."""
    return re.sub(r"[^a-z0-9]+", "-", ad.lower()).strip("-")


def _dayanaklar(gecmis: Gecmis, g: str) -> Dayanaklar:
    gun = gecmis.get(g)
    return dict(gun["dayanak"]) if gun else {}


def _onceki(gecmis: Gecmis, gun: date) -> str | None:
    onceki = [g for g in gunler(gecmis, gun) if g < gun.isoformat()]
    return onceki[-1] if onceki else None


def _sayfa(
    kok: Path,
    ad: str,
    baslik: str,
    aciklama: str,
    simdi: datetime,
    sutunlar: tuple[Sutun, ...],
    satirlar: list[dict[str, object]],
    suzgecler: tuple[str, ...] = (),
) -> Path:
    yol = sayfa_yaz(
        kok,
        BOLUM,
        ad,
        baslik=baslik,
        aciklama=aciklama,
        guncellendi=simdi,
        kaynaklar=[_BIST],
        sutunlar=sutunlar,
        satirlar=satirlar,
        suzgecler=suzgecler,
        grafik="cizgi",
    )
    return Path(yol)


def _seri(kok: Path, anahtar: str, noktalar: list[tuple[date, float]], ad: str, birim: str) -> str:
    seri_yaz(kok, BOLUM, anahtar, noktalar, ad=ad, birim=birim)
    return anahtar


def acik_sayfasi(kok: Path, gun: date, gecmis: Gecmis, simdi: datetime) -> Path:
    """Dayanak başına vadeli açık pozisyon: son gün, bir önceki güne göre değişim ve seri."""
    tum = gunler(gecmis, gun)
    son = _dayanaklar(gecmis, gun.isoformat())
    onceki_g = _onceki(gecmis, gun)
    onceki = _dayanaklar(gecmis, onceki_g) if onceki_g else {}
    secilen: list[tuple[float, dict[str, object]]] = []
    for d, e in sorted(son.items()):
        acik = e["vadeli_acik"]
        if acik <= 0:
            continue
        noktalar = [
            (date.fromisoformat(g), _dayanaklar(gecmis, g)[d]["vadeli_acik"])
            for g in tum
            if d in _dayanaklar(gecmis, g)
        ]
        seri = _seri(kok, f"acik-{_anahtar(d)}", noktalar, f"{d} vadeli açık pozisyon", "sözleşme")
        oncesi = onceki.get(d)
        degisim = acik - oncesi["vadeli_acik"] if oncesi else None
        yuzde = (
            degisim / oncesi["vadeli_acik"]
            if oncesi and degisim is not None and oncesi["vadeli_acik"]
            else None
        )
        secilen.append(
            (
                acik,
                {
                    "dayanak": d,
                    "acik": acik,
                    "degisim": degisim,
                    "yuzde": yuzde,
                    "hacim": e["vadeli_hacim"],
                    "seri": seri,
                },
            )
        )
    secilen.sort(key=lambda t: -t[0])
    sutunlar = (
        Sutun("dayanak", "Dayanak", "metin"),
        Sutun("acik", "Açık pozisyon", "sayi", 0),
        Sutun("degisim", "Önceki güne göre", "sayi", 0),
        Sutun("yuzde", "Değişim (%)", "yuzde", 2),
        Sutun("hacim", "Vadeli hacim (TL)", "sayi", 0),
    )
    return _sayfa(
        kok,
        "acik-pozisyon",
        "Vadeli açık pozisyon",
        f"{gun:%d.%m.%Y} tarihli bülten. Satıra tıklayınca dayanağın açık pozisyon geçmişi çizilir.",
        simdi,
        sutunlar,
        [r for _, r in secilen],
    )


def putcall_sayfasi(kok: Path, gun: date, gecmis: Gecmis, simdi: datetime) -> Path:
    """Dayanak başına put/call oranı (hacim ve açık pozisyon). Yalnız oran; yorum yoktur."""
    tum = gunler(gecmis, gun)
    son = _dayanaklar(gecmis, gun.isoformat())
    secilen: list[tuple[float, dict[str, object]]] = []
    for d, e in sorted(son.items()):
        if e["cagri_hacim"] <= 0:
            continue
        noktalar: list[tuple[date, float]] = []
        for g in tum:
            o = _dayanaklar(gecmis, g).get(d)
            if o and o["cagri_hacim"] > 0:
                noktalar.append((date.fromisoformat(g), o["put_hacim"] / o["cagri_hacim"]))
        seri = _seri(kok, f"putcall-{_anahtar(d)}", noktalar, f"{d} put/call hacim oranı", "oran")
        secilen.append(
            (
                e["cagri_hacim"],
                {
                    "dayanak": d,
                    "oran_hacim": e["put_hacim"] / e["cagri_hacim"],
                    "oran_acik": e["put_acik"] / e["cagri_acik"] if e["cagri_acik"] > 0 else None,
                    "cagri_hacim": e["cagri_hacim"],
                    "put_hacim": e["put_hacim"],
                    "seri": seri,
                },
            )
        )
    secilen.sort(key=lambda t: -t[0])
    sutunlar = (
        Sutun("dayanak", "Dayanak", "metin"),
        Sutun("oran_hacim", "Put/call (hacim)", "sayi", 2),
        Sutun("oran_acik", "Put/call (açık poz.)", "sayi", 2),
        Sutun("cagri_hacim", "Alım hacmi (TL)", "sayi", 0),
        Sutun("put_hacim", "Satım hacmi (TL)", "sayi", 0),
    )
    return _sayfa(
        kok,
        "put-call",
        "Put/call oranı",
        f"{gun:%d.%m.%Y} tarihli bülten. Oran, satım opsiyonlarının alım opsiyonlarına göre payıdır; yorum içermez.",
        simdi,
        sutunlar,
        [r for _, r in secilen],
    )


def takvim_sayfasi(kok: Path, gun: date, satirlar: list[ViopSatiri], simdi: datetime) -> Path:
    """Gelecek vade tarihleri: her vadedeki vadeli sözleşme sayısı, hacim ve açık pozisyon."""
    grup: dict[date, list[ViopSatiri]] = {}
    for s in satirlar:
        if vadeli_mi(s) and s.vade >= gun:
            grup.setdefault(s.vade, []).append(s)
    kayitlar: list[dict[str, object]] = [
        {
            "vade": v.isoformat(),
            "sozlesme": len(g),
            "hacim": sum(s.hacim_tl for s in g),
            "acik": sum(s.acik_pozisyon for s in g),
        }
        for v, g in sorted(grup.items())
    ]
    sutunlar = (
        Sutun("vade", "Vade", "tarih"),
        Sutun("sozlesme", "Vadeli sözleşme", "sayi", 0),
        Sutun("hacim", "Hacim (TL)", "sayi", 0),
        Sutun("acik", "Açık pozisyon", "sayi", 0),
    )
    return _sayfa(
        kok,
        "takvim",
        "Vade takvimi",
        f"{gun:%d.%m.%Y} tarihli bültendeki vadeli sözleşmelerin vade tarihleri.",
        simdi,
        sutunlar,
        kayitlar,
    )


def egri_sayfasi(kok: Path, gun: date, satirlar: list[ViopSatiri], simdi: datetime) -> Path:
    """Dayanak başına vade eğrisi: en yakın ve en uzak vade, seri olarak tüm eğri."""
    grup: dict[str, list[ViopSatiri]] = {}
    for s in satirlar:
        if vadeli_mi(s) and s.vade >= gun and s.uzlasma > 0:
            grup.setdefault(dayanak_kanonik(s), []).append(s)
    kayitlar: list[dict[str, object]] = []
    for d, g in sorted(grup.items()):
        g.sort(key=lambda s: s.vade)
        seri = _seri(
            kok,
            f"egri-{_anahtar(d)}",
            [(s.vade, s.uzlasma) for s in g],
            f"{d} vade eğrisi (uzlaşma)",
            "fiyat",
        )
        yakin, uzak = g[0], g[-1]
        kayitlar.append(
            {
                "dayanak": d,
                "sozlesme": len(g),
                "yakin_vade": yakin.vade.isoformat(),
                "yakin_uzlasma": yakin.uzlasma,
                "uzak_vade": uzak.vade.isoformat(),
                "uzak_uzlasma": uzak.uzlasma,
                "seri": seri,
            }
        )
    sutunlar = (
        Sutun("dayanak", "Dayanak", "metin"),
        Sutun("sozlesme", "Sözleşme", "sayi", 0),
        Sutun("yakin_vade", "En yakın vade", "tarih"),
        Sutun("yakin_uzlasma", "Uzlaşma (yakın)", "sayi", 2),
        Sutun("uzak_vade", "En uzak vade", "tarih"),
        Sutun("uzak_uzlasma", "Uzlaşma (uzak)", "sayi", 2),
    )
    return _sayfa(
        kok,
        "vade-egrisi",
        "Vade eğrisi",
        f"{gun:%d.%m.%Y} tarihli bülten. Grafik, vade tarihine göre uzlaşma fiyatlarını gösterir.",
        simdi,
        sutunlar,
        kayitlar,
    )


def varant_satirlari(
    pay: list[PaySatiri], spot: Mapping[str, float], gun: date, faiz: float | None
) -> list[dict[str, object]]:
    """Pay bültenindeki varantlar. Etkin kaldıraç yalnız dayanak fiyatı ve faiz varsa hesaplanır."""
    secilen: list[tuple[float, dict[str, object]]] = []
    for s in pay:
        if s.tip not in VARANT_TIPLERI or s.kapanis <= 0:
            continue
        v = varant_adi_coz(s.ad)
        if v is None:
            continue
        kaldirac: float | None = None
        fiyat = spot.get(v.dayanak)
        yil = (v.vade - gun).days / 365
        if faiz is not None and fiyat and yil > 0:
            oynaklik = ortuk_oynaklik(s.kapanis, fiyat, v.kullanim, yil, faiz, v.tur)
            if oynaklik is not None:
                delta = bs_delta(fiyat, v.kullanim, yil, faiz, oynaklik, v.tur)
                kaldirac = etkin_kaldirac(delta, fiyat, s.kapanis, v.carpan)
        secilen.append(
            (
                s.hacim_tl,
                {
                    "kod": s.kod,
                    "dayanak": v.dayanak,
                    "tur": _TUR[v.tur],
                    "vade": v.vade.isoformat(),
                    "kullanim": v.kullanim,
                    "kapanis": s.kapanis,
                    "hacim": s.hacim_tl,
                    "kaldirac": kaldirac,
                },
            )
        )
    secilen.sort(key=lambda t: -t[0])
    return [r for _, r in secilen]


def varant_sayfasi(
    kok: Path,
    gun: date,
    pay: list[PaySatiri],
    spot: Mapping[str, float],
    faiz: float | None,
    simdi: datetime,
) -> Path:
    sutunlar = (
        Sutun("kod", "Kod", "metin"),
        Sutun("dayanak", "Dayanak", "metin"),
        Sutun("tur", "Tür", "metin"),
        Sutun("vade", "Vade", "tarih"),
        Sutun("kullanim", "Kullanım", "sayi", 2),
        Sutun("kapanis", "Kapanış", "sayi", 2),
        Sutun("hacim", "Hacim (TL)", "sayi", 0),
        Sutun("kaldirac", "Etkin kaldıraç", "sayi", 2),
    )
    not_ = (
        "Etkin kaldıraç, dayanak fiyatı ve risksiz faiz verisi varsa hesaplanır."
        if faiz is not None
        else "Risksiz faiz verisi bu koşuda yok; etkin kaldıraç hesaplanmadı."
    )
    return _sayfa(
        kok,
        "varant",
        "Varantlar",
        f"{gun:%d.%m.%Y} tarihli pay bülteni. {not_}",
        simdi,
        sutunlar,
        varant_satirlari(pay, spot, gun, faiz),
        suzgecler=("dayanak", "tur"),
    )


def _ema(x: list[float], n: int) -> list[float | None]:
    """Üstel ortalama (pandas ewm(span=n, adjust=False) ile aynı); ilk n değerden önce boş."""
    out: list[float | None] = [None] * len(x)
    if len(x) < n:
        return out
    alfa = 2 / (n + 1)
    e = x[0]
    for i, v in enumerate(x):
        e = v if i == 0 else alfa * v + (1 - alfa) * e
        if i >= n - 1:
            out[i] = e
    return out


def _rsi(x: list[float], n: int = 14) -> list[float | None]:
    """Wilder RSI (yumuşatma alfa = 1/n); ilk n fark dolmadan boş."""
    out: list[float | None] = [None] * len(x)
    if len(x) <= n:
        return out
    fark = [x[i] - x[i - 1] for i in range(1, len(x))]
    alfa = 1 / n
    kazanc = max(fark[0], 0.0)
    kayip = max(-fark[0], 0.0)
    for i, f in enumerate(fark):
        if i:
            kazanc = alfa * max(f, 0.0) + (1 - alfa) * kazanc
            kayip = alfa * max(-f, 0.0) + (1 - alfa) * kayip
        if i + 1 >= n:
            out[i + 1] = 100.0 if kayip == 0 else 100 - 100 / (1 + kazanc / kayip)
    return out


def _haftalik(tarihler: list[date], fiyat: list[float]) -> tuple[list[date], list[float]]:
    """Her ISO haftanın son işlem günü ve kapanışı."""
    son: dict[tuple[int, int], tuple[date, float]] = {}
    for t, f in zip(tarihler, fiyat):
        yil, hafta, _ = t.isocalendar()
        son[(yil, hafta)] = (t, f)
    sirali = [son[k] for k in sorted(son)]
    return [t for t, _ in sirali], [f for _, f in sirali]


def _on_vade_serisi(
    tum: list[str], gecmis: Gecmis, d: str
) -> tuple[list[date], list[float], list[float]]:
    """Dayanağın ön vade serisi: (tarih, geriye uyarlanmış fiyat, ham fiyat).

    Ön vade yuvarlanınca (kod değişince) önceki günlerin fiyatı yeni sözleşmenin ayrımıyla çarpılır;
    böylece seri yuvarlama günlerinde sıçramaz. Ayrım, iki sözleşmenin de işlem gördüğü son günden alınır.
    """
    tarihler: list[date] = []
    ham: list[float] = []
    kodlar: list[str] = []
    uzlasmalar: list[dict[str, float]] = []
    for g in tum:
        gun = gecmis[g] or {}
        dd = gun.get("dayanak", {}).get(d, {})
        if "on_uzlasma" not in dd:
            continue
        tarihler.append(date.fromisoformat(g))
        ham.append(float(dd["on_uzlasma"]))
        kodlar.append(str(gun["on_kod"][d]))
        uzlasmalar.append({k: float(v) for k, v in gun.get("uzlasma", {}).items()})
    uyarli = [0.0] * len(ham)
    carpan = 1.0
    for i in range(len(ham) - 1, -1, -1):
        uyarli[i] = ham[i] * carpan
        if i and kodlar[i] != kodlar[i - 1]:
            eski = uzlasmalar[i - 1].get(kodlar[i - 1])
            yeni = uzlasmalar[i - 1].get(kodlar[i])
            if eski and yeni:
                carpan *= yeni / eski
    return tarihler, uyarli, ham


def on_vade_sayfasi(kok: Path, gun: date, gecmis: Gecmis, simdi: datetime) -> Path:
    """Dayanak başına ön vade fiyatı: günlük ve haftalık seri; EMA 144/233/377 ve RSI 14.

    Gösterge, yeterli geçmiş yoksa boş kalır (ör. 233 gün dolmadan EMA 233 yoktur).
    """
    tum = gunler(gecmis, gun)
    son = _dayanaklar(gecmis, gun.isoformat())
    secilen: list[tuple[float, dict[str, object]]] = []
    for d, e in sorted(son.items()):
        if "on_uzlasma" not in e:
            continue
        tarihler, fiyat, ham_fiyat = _on_vade_serisi(tum, gecmis, d)
        gunluk: dict[str, list[float | None]] = {
            "kapanis": [float(f) for f in fiyat],
            "ema144": _ema(fiyat, 144),
            "ema233": _ema(fiyat, 233),
            "ema377": _ema(fiyat, 377),
            "rsi14": _rsi(fiyat),
        }
        ht, hf = _haftalik(tarihler, fiyat)
        haftalik: dict[str, list[float | None]] = {
            "kapanis": [float(f) for f in hf],
            "ema144": _ema(hf, 144),
            "ema233": _ema(hf, 233),
            "rsi14": _rsi(hf),
        }
        anahtar = f"fiyat-{_anahtar(d)}"
        seri_cok_yaz(kok, BOLUM, anahtar, tarihler, gunluk, ad=f"{d} ön vade", birim="fiyat")
        seri_cok_yaz(
            kok,
            BOLUM,
            f"{anahtar}-hafta",
            ht,
            haftalik,
            ad=f"{d} ön vade (haftalık)",
            birim="fiyat",
        )
        yuzde = (fiyat[-1] / fiyat[-2] - 1) if len(fiyat) > 1 and fiyat[-2] else None
        secilen.append(
            (
                e["vadeli_hacim"],
                {
                    "dayanak": d,
                    "fiyat": ham_fiyat[-1],
                    "yuzde": yuzde,
                    "hacim": e["vadeli_hacim"],
                    "acik": e["vadeli_acik"],
                    "seri": anahtar,
                },
            )
        )
    secilen.sort(key=lambda t: -t[0])
    sutunlar = (
        Sutun("dayanak", "Dayanak", "metin"),
        Sutun("fiyat", "Ön vade fiyatı", "sayi", 2),
        Sutun("yuzde", "Değişim (%)", "yuzde", 2),
        Sutun("hacim", "Vadeli hacim (TL)", "sayi", 0),
        Sutun("acik", "Açık pozisyon", "sayi", 0),
    )
    return _sayfa(
        kok,
        "on-vade",
        "Ön vade fiyatı",
        f"{gun:%d.%m.%Y} tarihli bülten. Her dayanağın en çok işlem gören vadeli sözleşmesi; satıra tıklayınca grafik açılır.",
        simdi,
        sutunlar,
        [r for _, r in secilen],
    )


def ek_sayfalar(
    kok: Path,
    gun: date,
    satirlar: list[ViopSatiri],
    pay: list[PaySatiri],
    gecmis: Gecmis,
    spot: Mapping[str, float],
    faiz: float | None,
    simdi: datetime,
) -> list[Path]:
    """Ek sayfaların hepsini yazar. Bugünkü özet yoksa geçmişe dayanan sayfalar atlanır."""
    yollar = [takvim_sayfasi(kok, gun, satirlar, simdi), egri_sayfasi(kok, gun, satirlar, simdi)]
    if gecmis.get(gun.isoformat()):
        yollar.append(acik_sayfasi(kok, gun, gecmis, simdi))
        yollar.append(putcall_sayfasi(kok, gun, gecmis, simdi))
        yollar.append(on_vade_sayfasi(kok, gun, gecmis, simdi))
    yollar.append(varant_sayfasi(kok, gun, pay, spot, faiz, simdi))
    return yollar
