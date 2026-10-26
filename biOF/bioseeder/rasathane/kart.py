"""biOF kartları: olayları ve çalışmaları Rasathane'nin ortak Kâğıt kartına çevirir."""
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from bioseeder.rasathane.ctgov import Calisma, bitis_tarihi
from bioseeder.rasathane.olay import KEHRIBAR, KIRMIZI, RENK, Olay
from rasathane_ortak.kagit import Hucre, Kart, Satir

FIKIR = "biOF"
KAYNAK = "ClinicalTrials.gov · SEC EDGAR"
KART_BASINA = 6


@dataclass
class Kutucuk:
    ticker: str
    etiket: str
    renk: str  # olay türü; Kâğıt kartında yalnız kayıt için tutulur
    satir: str
    ayrinti: str
    mikro: bool
    ayrinti_renk: Optional[str] = None  # doluysa ayrıntı vurgulanır (ör. seyreltme riski)


def olay_kutucugu(o: Olay) -> Kutucuk:
    return Kutucuk(o.ticker, o.etiket, RENK[o.tur], o.satir, o.ayrinti, o.mikro)


def _ay_sayisi(x: float) -> str:
    return f"{x:.0f}" if x >= 10 else f"{x:.1f}".replace(".", ",")


def calisma_kutucugu(c: Calisma, bugun: date, nakit_pisti_ay: Optional[float], mikro: bool) -> Kutucuk:
    if c.bitis_hassas == "AY":
        etiket = f"{c.bitis[5:7]}.{c.bitis[:4]}"
    else:
        etiket = f"{(bitis_tarihi(c) - bugun).days} GÜN"
    renk = None
    if nakit_pisti_ay is None:
        ayrinti = "Nakit pisti: —"
    elif nakit_pisti_ay < 6:
        ayrinti, renk = f"SEYRELTME RİSKİ · {_ay_sayisi(nakit_pisti_ay)} ay", KIRMIZI
    else:
        ayrinti = f"Nakit pisti {_ay_sayisi(nakit_pisti_ay)} ay"
    return Kutucuk(c.ticker, etiket, KEHRIBAR, f"{c.ilac} · {c.hastalik} · Faz {c.faz}", ayrinti, mikro, renk)


def kutucuk_satiri(k: Kutucuk) -> Satir:
    vurgu = k.ayrinti_renk is not None
    return Satir(ust=k.ticker, etiket=k.etiket, alt=k.satir + (" · mikro" if k.mikro else ""),
                 sag=(Hucre(k.ayrinti, ikincil=not vurgu, vurgu=vurgu),) if k.ayrinti else ())


def kart(ad: str, tarih_metni: str, kutucuklar: List[Kutucuk], alt_baslik: str, not_: str = "",
         kaynak: str = KAYNAK) -> Kart:
    return Kart(fikir=FIKIR, ad=ad, tarih=tarih_metni, alt_baslik=alt_baslik, kaynak=kaynak,
                satirlar=tuple(kutucuk_satiri(k) for k in kutucuklar), not_=not_)
