# src/opsi/kanal/cizim.py
"""OPsi kartları: veriyi Rasathane'nin ortak Kâğıt kartına çevirir."""

import datetime

from rasathane_ortak import kagit
from rasathane_ortak.kagit import Hucre, Kart, Satir

from .kartlar import CspKarti, CspSatiri, PrimKarti, SarsintiSatiri

FIKIR = "OPsi"
KAYNAK = "Yahoo Finance"
# Sarsıntı kartı 8 satıra kadar çıkar; OPsi kartları sayfalanmaz, gerekirse uzar.
SAYFA_SATIRI = 10
_AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def tarih_tr(iso: str) -> str:
    y, a, g = iso.split("-")
    return f"{int(g)} {_AYLAR[int(a) - 1]} {y}"


def _tarih(iso: str) -> str:
    return kagit.tarih_metni(datetime.date.fromisoformat(iso))


def _sayi(x: float, basamak: int = 2) -> str:
    s = f"{x:,.{basamak}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _usd(x: float) -> str:
    return "$" + _sayi(x)


def _yuzde(x: float, basamak: int = 1, isaret: bool = False) -> str:
    s = _sayi(abs(x) * 100, basamak)
    on = ("+" if x >= 0 else "−") if isaret else ""
    return f"{on}%{s}"


def sarsinti_ciz(
    satirlar: list[SarsintiSatiri], tarih: str, onceki_tarih: str, sembol_sayisi: int
) -> Kart:
    once, bugun = datetime.date.fromisoformat(onceki_tarih), datetime.date.fromisoformat(tarih)
    return Kart(
        fikir=FIKIR,
        ad="IV Sarsıntısı",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=(
            f"Günün en sert IV hareketleri · {sembol_sayisi} sembol · "
            f"{once:%d.%m} ile {bugun:%d.%m} kapanışı"
        ),
        sutunlar=("Hisse", "Kapanış", "IV30", "Değişim"),
        satirlar=tuple(
            Satir(
                ust=r["sembol"],
                etiket="bilanço" if r["bilanco"] else "",
                alt=r["ad"],
                sag=(
                    Hucre(_usd(r["kapanis"]), alt=_yuzde(r["fiyat_degisim"], 2, True)),
                    Hucre(f"{round(r['iv_once'] * 100)}→{round(r['iv_simdi'] * 100)}"),
                    Hucre(_yuzde(r["iv_degisim"], 0, True), kalin=True, vurgu=True),
                ),
            )
            for r in satirlar
        ),
    )


def prim_ciz(kart: PrimKarti, tarih: str, sembol_sayisi: int) -> Kart:
    return Kart(
        fikir=FIKIR,
        ad="Aşağı Yön Primi",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=(
            f"Put satıcısının en çok prim aldığı hisseler · {sembol_sayisi} sembol, "
            f"ortanca {_sayi(kart['medyan'])}"
        ),
        sutunlar=("Hisse", "Kapanış", "Skew"),
        satirlar=tuple(
            Satir(
                ust=r["sembol"],
                alt=r["ad"],
                sag=(Hucre(_usd(r["kapanis"])), Hucre(_sayi(r["skew"]), kalin=True, vurgu=True)),
            )
            for r in kart["satirlar"]
        ),
    )


def csp_ciz(kart: CspKarti, tarih: str, hafta: str) -> Kart:
    def konum(r: CspSatiri) -> str:
        return "konum —" if r["iv_konum"] is None else f"konum %{round(r['iv_konum'] * 100)}"

    return Kart(
        fikir=FIKIR,
        ad=f"Nakit Teminatlı Put · {kart['bant']}",
        tarih=_tarih(tarih),
        kaynak=KAYNAK,
        alt_baslik=f"{hafta} haftası · 20–45 gün · {kart['iv_etiket']}",
        sutunlar=("Hisse", "Fiyat", "Beklenen hareket", "IV30", "Puan"),
        satirlar=tuple(
            Satir(
                ust=r["sembol"],
                alt=r["ad"],
                sag=(
                    Hucre(_usd(r["fiyat"]), kalin=True),
                    Hucre(
                        "±" + _yuzde(r["hareket_yuzde"]),
                        alt=f"{_usd(r['hareket_alt'])} – {_usd(r['hareket_ust'])}",
                    ),
                    Hucre(_sayi(r["iv30"] * 100, 1), alt=konum(r)),
                    Hucre(str(round(r["skor"])), kalin=True, vurgu=True),
                ),
            )
            for r in kart["satirlar"]
        ),
    )
