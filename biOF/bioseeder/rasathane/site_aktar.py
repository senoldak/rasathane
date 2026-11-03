"""Site verisi: biOF takvimi ve olaylarından `site-veri/biof/` JSON dosyaları.

Veri, Telegram kartlarını besleyen aynı sonuçlardan yazılır; gönderime bağlı değildir. Olaylar sayfası
son OLAY_GUN günü tutar: her koşu önceki sayfadaki satırları okur, yenilerini ekler, eskisini düşürür.
Hisse fiyatı çekilemezse o hissenin grafiği yazılmaz; satır grafiksiz kalır.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from rasathane_ortak.site import Kaynak, Sutun, sayfa_yaz, seri_cok_yaz

from bioseeder.rasathane.ctgov import Calisma, bitis_tarihi, yaklasanlar
from bioseeder.rasathane.olay import Olay

BOLUM = "biof"
TAKVIM = "takvim"
OLAYLAR = "olaylar"
TAKVIM_GUN = 60
OLAY_GUN = 365
SERI_AZAMI = 60  # bir koşuda en çok bu kadar hisse için fiyat çekilir
ISINMA_GUN = 5 * 365  # EMA 377 ve RSI'nin ilk değerleri oturabilsin diye geriye dönük fiyat
SERI_GUN = 252  # günlük seride gösterilen işlem günü
HAFTA_SAYI = 104  # haftalık seride gösterilen hafta

FiyatCekici = Callable[[str, date, date], list[tuple[date, float]]]

_CT = Kaynak("ClinicalTrials.gov", "https://clinicaltrials.gov/")
_SEC = Kaynak("SEC EDGAR", "https://www.sec.gov/")
_YAHOO = Kaynak("Yahoo Finance", "https://finance.yahoo.com/")
_OLAY_ALANLARI = ("tarih", "ticker", "etiket", "satir", "ayrinti", "mikro")

_TAKVIM_SUTUNLAR = [
    Sutun("ticker", "Hisse", "metin"),
    Sutun("ilac", "İlaç", "metin"),
    Sutun("hastalik", "Hastalık", "metin"),
    Sutun("faz", "Faz", "metin"),
    Sutun("bitis", "Tahmini bitiş", "metin"),
    Sutun("kalan_gun", "Kalan gün", "sayi", 0),
    Sutun("mikro", "Ölçek", "metin"),
]
_OLAY_SUTUNLAR = [
    Sutun("tarih", "Tarih", "tarih"),
    Sutun("ticker", "Hisse", "metin"),
    Sutun("etiket", "Olay", "metin"),
    Sutun("satir", "Konu", "metin"),
    Sutun("ayrinti", "Ayrıntı", "metin"),
    Sutun("mikro", "Ölçek", "metin"),
]


def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def _bitis_metni(c: Calisma) -> str:
    if c.bitis_hassas == "AY":
        return f"{c.bitis[5:7]}.{c.bitis[:4]}"
    b = bitis_tarihi(c)
    return f"{b:%d.%m.%Y}" if b else c.bitis


def _takvim_satiri(c: Calisma, bugun: date, mikro: Mapping[str, bool]) -> dict[str, object]:
    b = bitis_tarihi(c)
    gun_hassas = c.bitis_hassas == "GUN" and b is not None
    return {
        "ticker": c.ticker,
        "ilac": c.ilac,
        "hastalik": c.hastalik,
        "faz": c.faz,
        "bitis": _bitis_metni(c),
        "kalan_gun": (b - bugun).days if gun_hassas else None,
        "mikro": "MİKRO" if mikro.get(c.ticker, False) else "",
    }


def _olay_satiri(o: Olay) -> dict[str, object]:
    return {
        "tarih": o.tarih.isoformat(),
        "ticker": o.ticker,
        "etiket": o.etiket,
        "satir": o.satir,
        "ayrinti": o.ayrinti,
        "mikro": "MİKRO" if o.mikro else "",
    }


def _oku_satirlar(yol: Path) -> list[dict]:
    """Önceki sayfanın satırları; yoksa ya da bozuksa boş liste (sayfa sıfırdan kurulur)."""
    if not yol.exists():
        return []
    try:
        return list(json.loads(yol.read_text(encoding="utf-8")).get("satirlar", []))
    except (ValueError, AttributeError) as exc:
        print(f"biOF site: {yol.name} okunamadı, sıfırdan kuruluyor: {exc}", file=sys.stderr)
        return []


def _birlestir(eski: Sequence[dict], yeni: Sequence[dict], bugun: date) -> list[dict]:
    sinir = (bugun - timedelta(days=OLAY_GUN)).isoformat()
    kayitlar: dict[tuple[str, ...], dict] = {}
    for r in [*eski, *yeni]:
        satir = {k: r.get(k, "") for k in _OLAY_ALANLARI}
        if satir["tarih"] < sinir:
            continue
        kayitlar[(satir["tarih"], satir["ticker"], satir["etiket"], satir["satir"])] = satir
    return sorted(kayitlar.values(), key=lambda r: (r["tarih"], r["ticker"]), reverse=True)


def _isaretler(olay_satirlari: Sequence[Mapping[str, object]]) -> dict[str, list[tuple[date, str]]]:
    sonuc: dict[str, list[tuple[date, str]]] = {}
    for r in olay_satirlari:
        sonuc.setdefault(str(r["ticker"]), []).append((date.fromisoformat(str(r["tarih"])), str(r["etiket"])))
    return sonuc


def _seri_var(kok: Path, ticker: str) -> bool:
    return (kok / BOLUM / "seri" / f"{ticker}.json").exists()


def _seri_ekle(kok: Path, satir: dict) -> dict:
    """Grafiği yazılmış hisseye `seri` anahtarını verir; yoksa satır grafiksiz kalır."""
    return {**satir, "seri": satir["ticker"]} if _seri_var(kok, str(satir["ticker"])) else satir


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    """Wilder RSI (yumuşatma alpha = 1/n); emtia seti ile aynı tanım."""
    fark = c.diff()
    kazanc = fark.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    kayip = (-fark.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + kazanc / kayip)


def _son(df: pd.DataFrame, n: int) -> tuple[list[date], dict[str, list[float | None]]]:
    tarihler = [i.date() for i in df.index][-n:]
    sutunlar = {k: [None if pd.isna(v) else float(v) for v in df[k]][-n:] for k in df.columns}
    return tarihler, sutunlar


def _gostergeli_seri(kok: Path, ticker: str, kapanis: pd.Series, isaret: list[tuple[date, str]]) -> None:
    """Ortak gösterge seti (emtia ile aynı): EMA 144/233/377 ve RSI (14). Günlük ve haftalık iki dosya.
    Göstergeler tam geçmiş üzerinde hesaplanır, son 1 yıl (günlük) ve son 2 yıl (haftalık) yazılır."""
    gunluk = pd.DataFrame(
        {
            "kapanis": kapanis,
            "ema144": kapanis.ewm(span=144, adjust=False).mean(),
            "ema233": kapanis.ewm(span=233, adjust=False).mean(),
            "ema377": kapanis.ewm(span=377, adjust=False).mean(),
            "rsi14": _rsi(kapanis),
        }
    )
    t, s = _son(gunluk, SERI_GUN)
    seri_cok_yaz(kok, BOLUM, ticker, t, s, ad=ticker, birim="$", isaretler=isaret)

    h = kapanis.resample("W-FRI").last().dropna()
    haftalik = pd.DataFrame(
        {
            "kapanis": h,
            "ema144": h.ewm(span=144, adjust=False).mean(),
            "ema233": h.ewm(span=233, adjust=False).mean(),
            "rsi14": _rsi(h),
        }
    )
    t, s = _son(haftalik, HAFTA_SAYI)
    seri_cok_yaz(kok, BOLUM, f"{ticker}-hafta", t, s, ad=ticker, birim="$", isaretler=isaret)


def _seriler(
    kok: Path,
    tickerlar: Sequence[str],
    isaretler: Mapping[str, list[tuple[date, str]]],
    bugun: date,
    fiyat: FiyatCekici,
) -> None:
    """Her hisse için kapanış ve gösterge serileri; olay günleri çizgide işaretlenir. Tek hissenin hatası
    yalnız o hissenin grafiğini atlatır."""
    bas = bugun - timedelta(days=ISINMA_GUN)
    for t in list(dict.fromkeys(tickerlar))[:SERI_AZAMI]:
        try:
            fiyatlar = fiyat(t, bas, bugun + timedelta(days=1))
            if not fiyatlar:
                continue
            kapanis = pd.Series(
                [float(v) for _, v in fiyatlar], index=pd.to_datetime([g for g, _ in fiyatlar]), dtype=float
            ).sort_index()
            kapanis = kapanis[~kapanis.index.duplicated(keep="last")]
            tarihler = set(kapanis.index.date)
            isaret = [(g, m) for g, m in isaretler.get(t, []) if g in tarihler]
            _gostergeli_seri(kok, t, kapanis, isaret)
        except Exception as exc:  # noqa: BLE001 — fiyat kaynağı tek hisseyi düşürebilir, sayfa düşmez
            print(f"biOF site: {t} fiyatı alınamadı: {type(exc).__name__}: {exc}", file=sys.stderr)


def takvim_aktar(
    kok: Path,
    bugun: date,
    goruntu: Mapping[str, Calisma],
    mikro: Mapping[str, bool],
    fiyat: Optional[FiyatCekici] = None,
    simdi: Optional[datetime] = None,
) -> Path:
    """`kok/biof/takvim.json`: bugünden itibaren TAKVIM_GUN gün içinde bitişi beklenen Faz 2 ve 3 çalışmaları."""
    liste = yaklasanlar(goruntu, bugun, TAKVIM_GUN)
    if fiyat is not None:
        isaretler = _isaretler(_oku_satirlar(kok / BOLUM / f"{OLAYLAR}.json"))
        _seriler(kok, [c.ticker for c in liste], isaretler, bugun, fiyat)
    satirlar = [_seri_ekle(kok, _takvim_satiri(c, bugun, mikro)) for c in liste]
    return sayfa_yaz(
        kok,
        BOLUM,
        TAKVIM,
        baslik="Önümüzdeki 60 gün",
        aciklama="Bitiş tarihi önümüzdeki 60 gün içinde olan Faz 2 ve Faz 3 çalışmaları. Tarihler şirketin "
        "ClinicalTrials.gov tahminidir; sonuç açıklama tarihi değildir.",
        guncellendi=simdi or _simdi(),
        kaynaklar=[_CT, _YAHOO],
        sutunlar=_TAKVIM_SUTUNLAR,
        satirlar=satirlar,
        suzgecler=["faz"],
    )


def olaylar_aktar(
    kok: Path,
    bugun: date,
    olaylar: Sequence[Olay],
    fiyat: Optional[FiyatCekici] = None,
    simdi: Optional[datetime] = None,
) -> Path:
    """`kok/biof/olaylar.json`: son OLAY_GUN günün faz ve FDA olayları. Bu koşunun olayları önceki sayfanın
    satırlarına eklenir; her olay yalnız bir kez durur, yeniden koşu sayfayı bozmaz."""
    satirlar = _birlestir(_oku_satirlar(kok / BOLUM / f"{OLAYLAR}.json"), [_olay_satiri(o) for o in olaylar], bugun)
    if fiyat is not None and olaylar:
        _seriler(kok, [o.ticker for o in olaylar], _isaretler(satirlar), bugun, fiyat)
    return sayfa_yaz(
        kok,
        BOLUM,
        OLAYLAR,
        baslik="Olaylar",
        aciklama="Son 365 günde ClinicalTrials.gov kayıtlarında ve SEC 8-K bildirimlerinde görülen faz ve FDA "
        "olayları. Hisse grafiklerinde olay günleri işaretlidir.",
        guncellendi=simdi or _simdi(),
        kaynaklar=[_CT, _SEC, _YAHOO],
        sutunlar=_OLAY_SUTUNLAR,
        satirlar=[_seri_ekle(kok, r) for r in satirlar],
        suzgecler=["etiket"],
    )
