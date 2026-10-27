"""İzlenen emtialar (Yahoo sürekli vadeli kontratları) ve oranlar."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Emtia:
    sembol: str
    ad: str
    grup: str
    birim: str


EMTIALAR: tuple[Emtia, ...] = (
    Emtia("GC=F", "Altın", "Değerli metaller", "$/ons"),
    Emtia("SI=F", "Gümüş", "Değerli metaller", "$/ons"),
    Emtia("PL=F", "Platin", "Değerli metaller", "$/ons"),
    Emtia("PA=F", "Paladyum", "Değerli metaller", "$/ons"),
    Emtia("BZ=F", "Brent petrol", "Enerji", "$/varil"),
    Emtia("CL=F", "WTI petrol", "Enerji", "$/varil"),
    Emtia("NG=F", "Doğalgaz", "Enerji", "$/MMBtu · Henry Hub"),
    Emtia("RB=F", "Benzin", "Enerji", "$/galon · RBOB"),
    Emtia("HO=F", "Dizel", "Enerji", "$/galon · ısınma yakıtı"),
    Emtia("HG=F", "Bakır", "Sanayi metalleri", "$/libre"),
    Emtia("ALI=F", "Alüminyum", "Sanayi metalleri", "$/ton"),
    Emtia("ZW=F", "Buğday", "Tarım", "¢/buşel"),
    Emtia("ZC=F", "Mısır", "Tarım", "¢/buşel"),
    Emtia("ZS=F", "Soya", "Tarım", "¢/buşel"),
    Emtia("KC=F", "Kahve", "Tarım", "¢/libre"),
    Emtia("CC=F", "Kakao", "Tarım", "$/ton"),
    Emtia("SB=F", "Şeker", "Tarım", "¢/libre"),
    Emtia("CT=F", "Pamuk", "Tarım", "¢/libre"),
    Emtia("LE=F", "Canlı sığır", "Hayvancılık", "¢/libre"),
    Emtia("HE=F", "Domuz", "Hayvancılık", "¢/libre"),
)
ADLAR = {e.sembol: e for e in EMTIALAR}

USDTRY = "TRY=X"
DOLAR_ENDEKSI = "DX-Y.NYB"
TUM_SEMBOLLER = [e.sembol for e in EMTIALAR] + [USDTRY, DOLAR_ENDEKSI]

ONS_GRAM = 31.1034768


@dataclass(frozen=True)
class Oran:
    anahtar: str
    ad: str
    pay: str
    payda: str
    anlam: str


ORANLAR: tuple[Oran, ...] = (
    Oran("altin_gumus", "Altın / gümüş", "GC=F", "SI=F", "yükselişi korku göstergesi"),
    Oran("bakir_altin", "Bakır / altın", "HG=F", "GC=F", "büyüme beklentisinin göstergesi"),
    Oran("brent_gaz", "Brent / doğalgaz", "BZ=F", "NG=F", "petrolün gaza göre pahalılığı"),
    Oran("brent_wti", "Brent / WTI", "BZ=F", "CL=F", "küresel ve ABD petrolü farkı"),
)
