import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Tuple

from bioseeder.rasathane.http import Istemci, KaynakHatasi

_SATIR = re.compile(r"^(\S+(?: \S+)*?)\s{2,}(.+?)\s{2,}(\d+)\s+(\d{8})\s+(edgar/\S+)\s*$")
_ATOM = "{http://www.w3.org/2005/Atom}"
_BASLIK = re.compile(r"^8-K - (.+) \((\d{10})\) \(Filer\)$")


@dataclass
class Bildirim:
    erisim: str
    cik: int
    ad: str
    tarih: date

    @property
    def baglanti(self) -> str:
        return (f"https://www.sec.gov/Archives/edgar/data/{self.cik}/"
                f"{self.erisim.replace('-', '')}/{self.erisim}-index.htm")


def gunluk_8k(ist: Istemci, gun: date) -> List[Bildirim]:
    url = (f"https://www.sec.gov/Archives/edgar/daily-index/{gun.year}/QTR{(gun.month - 1) // 3 + 1}/"
           f"form.{gun:%Y%m%d}.idx")
    try:
        metin = ist.metin(url, sec=True)
    except KaynakHatasi as exc:
        raise KaynakHatasi(f"EDGAR günlük dizini okunamadı ({gun.isoformat()}): {exc}", exc.durum) from exc
    sonuc = []
    for satir in metin.splitlines():
        m = _SATIR.match(satir)
        if not m or m.group(1) != "8-K":
            continue
        erisim = m.group(5).rsplit("/", 1)[-1].removesuffix(".txt")
        sonuc.append(Bildirim(erisim, int(m.group(3)), m.group(2).strip(),
                              datetime.strptime(m.group(4), "%Y%m%d").date()))
    return sonuc


def _akis_sayfasi(ist: Istemci, bas: int) -> List[Bildirim]:
    metin = ist.metin("https://www.sec.gov/cgi-bin/browse-edgar", params={
        "action": "getcurrent", "type": "8-K", "company": "", "dateb": "", "owner": "include",
        "start": str(bas), "count": "100", "output": "atom"}, sec=True)
    try:
        kok = ET.fromstring(metin.encode("utf-8") if metin.lstrip().startswith("<?xml") else metin)
    except ET.ParseError as exc:
        raise KaynakHatasi(f"EDGAR güncel akış ayrıştırılamadı: {exc}") from exc
    sonuc = []
    for e in kok.iter(f"{_ATOM}entry"):
        m = _BASLIK.match((e.findtext(f"{_ATOM}title") or "").strip())
        kimlik = e.findtext(f"{_ATOM}id") or ""
        if not m or "accession-number=" not in kimlik:
            continue
        tarih = date.fromisoformat((e.findtext(f"{_ATOM}updated") or "")[:10])
        sonuc.append(Bildirim(kimlik.split("accession-number=")[-1], int(m.group(2)), m.group(1), tarih))
    return sonuc


def guncel_8k(ist: Istemci, imlec: Optional[str], en_fazla_sayfa: int = 10) -> Tuple[List[Bildirim], Optional[str]]:
    sonuc: List[Bildirim] = []
    gorulen = set()
    for sayfa in range(en_fazla_sayfa if imlec else 1):
        kayitlar = _akis_sayfasi(ist, sayfa * 100)
        if not kayitlar:
            break
        for b in kayitlar:
            if b.erisim == imlec:
                return sonuc, (sonuc[0].erisim if sonuc else imlec)
            if b.erisim not in gorulen:
                gorulen.add(b.erisim)
                sonuc.append(b)
    return sonuc, (sonuc[0].erisim if sonuc else imlec)


_BELGE = re.compile(r"<DOCUMENT>\s*<TYPE>([^\s<]+).*?<TEXT>(.*?)</TEXT>", re.S | re.I)


def _duz_metin(s: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def bulten_metni(ist: Istemci, b: Bildirim) -> str:
    metin = ist.metin(f"https://www.sec.gov/Archives/edgar/data/{b.cik}/{b.erisim}.txt", sec=True)
    parcalar = [_duz_metin(govde) for tur, govde in _BELGE.findall(metin) if tur.upper().startswith("EX-99")]
    return " ".join(p for p in parcalar if p)
