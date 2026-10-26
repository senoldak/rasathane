"""Kart ve mesajlar için Türkçe sayı ve tarih biçimleri."""
from datetime import date
from typing import List

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _tr_sayi(x: float, basamak: int) -> str:
    """1234.5 -> '1.234,50' (Türkçe binlik nokta, ondalık virgül)."""
    return f"{x:,.{basamak}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def para(usd: float) -> str:
    if usd >= 1e9:
        return f"${_tr_sayi(usd / 1e9, 2)} Mr"
    if usd >= 1e6:
        return f"${_tr_sayi(usd / 1e6, 2)} Mn"
    return f"${_tr_sayi(round(usd / 1e3), 0)} Bin"


def fiyat(x: float) -> str:
    return _tr_sayi(x, 2)


def yuzde(x: float) -> str:
    if x >= 10:
        return "+999%+"
    return f"+{round(x * 100)}%"


def tarih_uzun(g: date) -> str:
    return f"{g.day} {AYLAR[g.month - 1]} {g.year}"


def tarih_kisa(g: date) -> str:
    return g.strftime("%d.%m.%Y")


def gun_adi(g: date) -> str:
    return GUNLER[g.weekday()]


def hafta_araligi(gunler: List[date]) -> str:
    ilk, son = gunler[0], gunler[-1]
    if ilk.month == son.month:
        return f"{ilk.day}–{son.day} {AYLAR[son.month - 1]} {son.year}"
    return f"{ilk.day} {AYLAR[ilk.month - 1]} – {tarih_uzun(son)}"
