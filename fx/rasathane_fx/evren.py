"""İzlenen kurlar (Yahoo), para birimlerinin ülke kodları (BIS) ve yardımcı semboller."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Kur:
    sembol: str
    ad: str
    grup: str
    para: str  # ölçülen para birimi (USD karşısında gücü hesaplanır)
    usd_bazli: bool  # USD/XXX kotasyonu: kur yükselince para birimi değer kaybeder


KURLAR: tuple[Kur, ...] = (
    Kur("EURUSD=X", "EUR/USD", "Majörler", "EUR", False),
    Kur("JPY=X", "USD/JPY", "Majörler", "JPY", True),
    Kur("GBPUSD=X", "GBP/USD", "Majörler", "GBP", False),
    Kur("CHF=X", "USD/CHF", "Majörler", "CHF", True),
    Kur("AUDUSD=X", "AUD/USD", "Majörler", "AUD", False),
    Kur("CAD=X", "USD/CAD", "Majörler", "CAD", True),
    Kur("NZDUSD=X", "NZD/USD", "Majörler", "NZD", False),
    Kur("EURJPY=X", "EUR/JPY", "Çaprazlar", "", False),
    Kur("EURGBP=X", "EUR/GBP", "Çaprazlar", "", False),
    Kur("EURCHF=X", "EUR/CHF", "Çaprazlar", "", False),
    Kur("NOK=X", "USD/NOK", "Avrupa", "NOK", True),
    Kur("SEK=X", "USD/SEK", "Avrupa", "SEK", True),
    Kur("PLN=X", "USD/PLN", "Avrupa", "PLN", True),
    Kur("HUF=X", "USD/HUF", "Avrupa", "HUF", True),
    Kur("CNY=X", "USD/CNY", "Gelişen ülkeler", "CNY", True),
    Kur("INR=X", "USD/INR", "Gelişen ülkeler", "INR", True),
    Kur("KRW=X", "USD/KRW", "Gelişen ülkeler", "KRW", True),
    Kur("MXN=X", "USD/MXN", "Gelişen ülkeler", "MXN", True),
    Kur("BRL=X", "USD/BRL", "Gelişen ülkeler", "BRL", True),
    Kur("ZAR=X", "USD/ZAR", "Gelişen ülkeler", "ZAR", True),
    Kur("TRY=X", "USD/TRY", "Türk lirası", "TRY", True),
    Kur("EURTRY=X", "EUR/TRY", "Türk lirası", "", False),
    Kur("GBPTRY=X", "GBP/TRY", "Türk lirası", "", False),
    Kur("DX-Y.NYB", "Dolar endeksi", "Dolar", "", False),
)
ADLAR = {k.sembol: k for k in KURLAR}
PARA_KURU = {k.para: k for k in KURLAR if k.para}

USDTRY, EURTRY, DXY = "TRY=X", "EURTRY=X", "DX-Y.NYB"
SEPET = "sepet"  # (USD/TRY + EUR/TRY) / 2, hesaplanır

BAKIR, WTI, BRENT, ABD10 = "HG=F", "CL=F", "BZ=F", "^TNX"
BIST100 = "XU100.IS"
YARDIMCI = [BAKIR, WTI, BRENT, ABD10]
TUM_SEMBOLLER = [k.sembol for k in KURLAR] + YARDIMCI

# BIS politika faizi ülke kodları
ULKE = {
    "USD": "US",
    "EUR": "XM",
    "JPY": "JP",
    "GBP": "GB",
    "CHF": "CH",
    "AUD": "AU",
    "CAD": "CA",
    "NZD": "NZ",
    "NOK": "NO",
    "SEK": "SE",
    "PLN": "PL",
    "HUF": "HU",
    "CNY": "CN",
    "INR": "IN",
    "KRW": "KR",
    "MXN": "MX",
    "BRL": "BR",
    "ZAR": "ZA",
    "TRY": "TR",
}

GUVENLI = ("JPY", "CHF")
RISKLI = ("AUD", "NZD", "MXN", "ZAR", "BRL")


@dataclass(frozen=True)
class Bag:
    anahtar: str
    ad: str
    kur: str
    dis: str
    dis_ad: str
    fark: bool = False  # dış seri faiz: getiri yerine günlük fark


BAGLAR: tuple[Bag, ...] = (
    Bag("aud_bakir", "AUD – bakır", "AUDUSD=X", BAKIR, "Bakır vadeli"),
    Bag("cad_petrol", "CAD – WTI petrol", "CAD=X", WTI, "WTI vadeli"),
    Bag("nok_brent", "NOK – Brent", "NOK=X", BRENT, "Brent vadeli"),
    Bag("jpy_faiz", "USD/JPY – ABD 10 yıllık", "JPY=X", ABD10, "ABD 10 yıllık faizi", fark=True),
)
