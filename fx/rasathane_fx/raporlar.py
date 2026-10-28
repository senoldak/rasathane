"""Dış kaynaklar: BIS politika faizleri, 2 yıllık devlet tahvili faizleri (FRED, ECB, Japonya
Maliye Bakanlığı), CFTC TFF raporu ve Borsa İstanbul pay bülteni. Hepsi anahtarsız açık kaynak."""

import csv
import datetime
import io
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from .evren import ULKE

_ZAMAN_ASIMI = 60
BIS_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.{ulkeler}"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ECB_URL = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y"
MOF_URLLER = (
    "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
    "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv",
)
CFTC_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
COT_HAFTA = 156  # 3 yıl
COT_UC = 0.05

MetinAl = Callable[[str, dict[str, str]], str]
JsonAl = Callable[[str, dict[str, str]], Any]


def metin_al(url: str, parametre: dict[str, str]) -> str:
    y = requests.get(url, params=parametre, timeout=_ZAMAN_ASIMI)
    y.raise_for_status()
    y.encoding = y.encoding or "utf-8"
    return y.text


def json_al(url: str, parametre: dict[str, str]) -> Any:
    y = requests.get(url, params=parametre, timeout=_ZAMAN_ASIMI)
    y.raise_for_status()
    return y.json()


def politika_faizleri(al: MetinAl = metin_al) -> dict[str, float]:
    """para birimi → BIS'in son politika faizi (yüzde)."""
    ters = {u: p for p, u in ULKE.items()}
    metin = al(
        BIS_URL.format(ulkeler="+".join(ULKE.values())),
        {"lastNObservations": "1", "format": "csvfile", "detail": "dataonly"},
    )
    out: dict[str, float] = {}
    for r in csv.DictReader(io.StringIO(metin)):
        if r.get("OBS_VALUE") and r.get("REF_AREA") in ters:
            out[ters[r["REF_AREA"]]] = float(r["OBS_VALUE"])
    return out


def abd_2y(al: MetinAl = metin_al) -> pd.Series:
    df = pd.read_csv(io.StringIO(al(FRED_URL, {"id": "DGS2"})), na_values=".")
    df.columns = ["tarih", "deger"]
    return _seri(df["tarih"], df["deger"])


def euro_2y(al: MetinAl = metin_al) -> pd.Series:
    """Euro bölgesi AAA devlet tahvili 2 yıllık spot faizi (ECB, Almanya'ya yakın)."""
    bas = (
        datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=800)
    ).isoformat()
    metin = al(ECB_URL, {"format": "csvdata", "detail": "dataonly", "startPeriod": bas})
    df = pd.read_csv(io.StringIO(metin))
    return _seri(df["TIME_PERIOD"], df["OBS_VALUE"])


def japonya_2y(al: MetinAl = metin_al) -> pd.Series:
    parcalar = []
    for url in MOF_URLLER:
        satirlar = al(url, {}).splitlines()
        bas = next(i for i, s in enumerate(satirlar) if s.startswith("Date,"))
        df = pd.read_csv(io.StringIO("\n".join(satirlar[bas:])), na_values="-")
        df = df[df["Date"].astype(str).str.match(r"^\d{4}/\d{1,2}/\d{1,2}$")]
        parcalar.append(_seri(pd.to_datetime(df["Date"], format="%Y/%m/%d"), df["2Y"]))
    s: pd.Series = pd.concat(parcalar).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def _seri(tarih: Any, deger: Any) -> pd.Series:
    s = pd.Series(pd.to_numeric(deger, errors="coerce").values, index=pd.to_datetime(tarih))
    return s.dropna().astype(float).sort_index()


COT_KODLARI: tuple[tuple[str, str], ...] = (
    ("099741", "EUR"),
    ("097741", "JPY"),
    ("096742", "GBP"),
    ("092741", "CHF"),
    ("090741", "CAD"),
    ("232741", "AUD"),
    ("112741", "NZD"),
    ("095741", "MXN"),
    ("102741", "BRL"),
    ("122741", "ZAR"),
    ("098662", "DXY"),
)


@dataclass(frozen=True)
class Pozisyon:
    para: str
    donem: str
    net: int
    degisim: int
    yuzdelik: float  # son 3 yılda bu haftanın net pozisyonunun altında kalan haftaların payı
    acik: int

    @property
    def uc(self) -> bool:
        return self.yuzdelik <= COT_UC or self.yuzdelik >= 1 - COT_UC


def cot(kod: str, para: str, al: JsonAl = json_al) -> Pozisyon:
    """Kaldıraçlı fonların (leveraged money) net vadeli pozisyonu."""
    satirlar = al(
        CFTC_URL,
        {
            "$select": "report_date_as_yyyy_mm_dd,lev_money_positions_long,"
            "lev_money_positions_short,open_interest_all",
            "$where": f"cftc_contract_market_code='{kod}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(COT_HAFTA + 1),
        },
    )
    if len(satirlar) < 2:
        raise ValueError(f"CFTC {kod}: yeterli veri yok")
    netler = [
        int(r["lev_money_positions_long"]) - int(r["lev_money_positions_short"]) for r in satirlar
    ]
    gecmis = netler[1:]
    return Pozisyon(
        para=para,
        donem=str(satirlar[0]["report_date_as_yyyy_mm_dd"])[:10],
        net=netler[0],
        degisim=netler[0] - netler[1],
        yuzdelik=sum(n < netler[0] for n in gecmis) / len(gecmis),
        acik=int(satirlar[0]["open_interest_all"]),
    )


def bist_evreni(bugun: datetime.date, adet: int = 100) -> list[str]:
    """Son pay bülteninde işlem hacmi en yüksek `adet` pay (Yahoo kodu: THYAO.IS)."""
    from rasathane_bist.bulten import pay_bulteni_oku
    from rasathane_bist.indir import dosya_al, pay_bulteni_url

    def indirici(url: str) -> tuple[int, bytes]:
        y = requests.get(url, timeout=_ZAMAN_ASIMI)
        return y.status_code, y.content

    for geri in range(10):
        gun = bugun - datetime.timedelta(days=geri)
        zip_ = dosya_al(indirici, pay_bulteni_url(gun))
        if zip_ is None:
            continue
        _, satirlar = pay_bulteni_oku(zip_)
        paylar = sorted(
            (
                s
                for s in satirlar
                if s.tip == "MSPOTEQT" and s.kod.endswith(".E") and s.hacim_tl > 0
            ),
            key=lambda s: -s.hacim_tl,
        )
        return [f"{s.kod.removesuffix('.E')}.IS" for s in paylar[:adet]]
    raise ValueError("pay bülteni bulunamadı")


EVDS_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
REZERVLER = (("TP.AB.C1", "Altın"), ("TP.AB.C2", "Döviz"), ("TP.AB.TOPLAM", "Toplam"))
AKIMLAR = (
    ("TP.MKNETHAR.M7", "Hisse senedi"),
    ("TP.MKNETHAR.M8", "DİBS"),
    ("TP.MKNETHAR.M12", "Özel sektör borçlanma senetleri"),
    ("TP.MKNETHAR.M22", "Yurt dışı ihraçlar"),
    ("TP.MKNETHAR.M20", "Toplam"),
)
REEL_KURLAR = (
    ("TP.RK.T1.Y", "TÜFE bazlı"),
    ("TP.RK.T2.Y", "TÜFE · gelişmekte olan ülkeler"),
    ("TP.RK.T3.Y", "TÜFE · gelişmiş ülkeler"),
    ("TP.RK.U01.Y", "Yİ-ÜFE bazlı"),
)

EvdsAl = Callable[[str, dict[str, str]], Any]


def evds_json_al(yol: str, baslik: dict[str, str]) -> Any:
    y = requests.get(EVDS_URL + yol, headers=baslik, timeout=_ZAMAN_ASIMI)
    y.raise_for_status()
    return y.json()


def evds(
    kodlar: list[str], bas: datetime.date, anahtar: str, al: EvdsAl = evds_json_al
) -> pd.DataFrame:
    """EVDS serileri; satır dizini dönem başı ya da hafta tarihi, sütunlar seri kodu."""
    bit = bas + datetime.timedelta(days=366 * 8)
    yol = f"series={'-'.join(kodlar)}&startDate={bas:%d-%m-%Y}&endDate={bit:%d-%m-%Y}&type=json"
    ogeler = al(yol, {"key": anahtar})["items"]
    satirlar = {}
    for o in ogeler:
        t = str(o["Tarih"])
        tarih = pd.to_datetime(t, format="%d-%m-%Y" if t.count("-") == 2 else "%Y-%m")
        satirlar[tarih] = {
            k: pd.to_numeric(o.get(k.replace(".", "_")), errors="coerce") for k in kodlar
        }
    df = pd.DataFrame.from_dict(satirlar, orient="index").sort_index()
    return df.dropna(how="all")
