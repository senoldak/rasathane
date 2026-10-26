import csv
from dataclasses import asdict, dataclass, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set

from bioseeder.rasathane.evren import Sirket, ad_normallestir
from bioseeder.rasathane.http import Istemci
from bioseeder.rasathane.olay import Olay, OlayTuru

API = "https://clinicaltrials.gov/api/v2/studies"
SORGU_ALANLARI = ",".join([
    "NCTId", "LeadSponsorName", "LeadSponsorClass", "Phase", "OverallStatus",
    "PrimaryCompletionDate", "LastUpdatePostDate", "StudyFirstPostDate", "HasResults", "InterventionName", "Condition",
])
DURMUS = {"TERMINATED", "SUSPENDED", "WITHDRAWN"}
KAPALI = DURMUS | {"COMPLETED"}
KAYMA_ESIK_GUN = 30


@dataclass
class Calisma:
    nct: str
    ticker: str
    faz: str
    durum: str
    bitis: str
    bitis_hassas: str
    sonuc: bool
    ilac: str
    hastalik: str
    ilk_kayit: str = ""  # StudyFirstPostDate, YYYY-AA-GG

    @property
    def faz3(self) -> bool:
        return self.faz in ("3", "2/3")


def sorgu(guncelleme: Optional[date]) -> Dict[str, Any]:
    filtre = ("AREA[LeadSponsorClass]INDUSTRY AND AREA[StudyType]INTERVENTIONAL"
              " AND (AREA[Phase]PHASE2 OR AREA[Phase]PHASE3)")
    if guncelleme:
        filtre += f" AND AREA[LastUpdatePostDate]{guncelleme.isoformat()}"
    return {"filter.advanced": filtre, "fields": SORGU_ALANLARI, "pageSize": 1000}


def _faz(fazlar: List[str]) -> Optional[str]:
    if "PHASE3" in fazlar:
        return "2/3" if "PHASE2" in fazlar else "3"
    if "PHASE2" in fazlar:
        return "2"
    return None


def _ayristir(cal: Mapping[str, Any], sponsorlar: Mapping[str, Sirket], eslesmeyen: Set[str]) -> Optional[Calisma]:
    p = cal.get("protocolSection", {})
    faz = _faz(p.get("designModule", {}).get("phases", []))
    if faz is None:
        return None
    sponsor = p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", "")
    sirket = sponsorlar.get(ad_normallestir(sponsor))
    if sirket is None:
        if sponsor:
            eslesmeyen.add(sponsor)
        return None
    durum_m = p.get("statusModule", {})
    bitis = durum_m.get("primaryCompletionDateStruct", {}).get("date", "")
    ilaclar = p.get("armsInterventionsModule", {}).get("interventions", [])
    hastaliklar = p.get("conditionsModule", {}).get("conditions", [])
    return Calisma(
        nct=p["identificationModule"]["nctId"],
        ticker=sirket.ticker,
        faz=faz,
        durum=durum_m.get("overallStatus", ""),
        bitis=bitis,
        bitis_hassas="AY" if len(bitis) == 7 else "GUN",
        sonuc=bool(cal.get("hasResults")),
        ilac=ilaclar[0].get("name", "") if ilaclar else "",
        hastalik=hastaliklar[0] if hastaliklar else "",
        ilk_kayit=durum_m.get("studyFirstPostDateStruct", {}).get("date", ""),
    )


def calismalari_cek(ist: Istemci, sorgu_param: Dict[str, Any], sponsorlar: Mapping[str, Sirket],
                    eslesmeyen: Set[str]) -> List[Calisma]:
    sonuc: List[Calisma] = []
    params = dict(sorgu_param)
    while True:
        sayfa = ist.json(API, params=params)
        for cal in sayfa.get("studies", []):
            c = _ayristir(cal, sponsorlar, eslesmeyen)
            if c:
                sonuc.append(c)
        jeton = sayfa.get("nextPageToken")
        if not jeton:
            return sonuc
        params["pageToken"] = jeton


_ALANLAR = [f.name for f in fields(Calisma)]


def goruntu_oku(yol: Path) -> Dict[str, Calisma]:
    if not yol.exists():
        return {}
    with yol.open(encoding="utf-8", newline="") as f:
        return {r["nct"]: Calisma(**{**r, "sonuc": r["sonuc"] == "1"}) for r in csv.DictReader(f)}


def goruntu_yaz(d: Mapping[str, Calisma], yol: Path) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    with yol.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_ALANLAR)
        w.writeheader()
        for nct in sorted(d):
            w.writerow({**asdict(d[nct]), "sonuc": "1" if d[nct].sonuc else "0"})


def bitis_tarihi(c: Calisma) -> Optional[date]:
    try:
        if c.bitis_hassas == "AY":
            return date.fromisoformat(c.bitis + "-15")
        return date.fromisoformat(c.bitis)
    except ValueError:
        return None


def _ay(c: Calisma) -> str:
    return f"{c.bitis[5:7]}.{c.bitis[:4]}"


def fark(eski: Mapping[str, Calisma], yeni: List[Calisma], gun: date, mikro: Mapping[str, bool]) -> List[Olay]:
    olaylar: List[Olay] = []

    def ekle(c: Calisma, tur: OlayTuru, ayrinti: str) -> None:
        etiket_ek = "FAZ 2/3" if c.faz == "2/3" and tur in (OlayTuru.YENI_FAZ3, OlayTuru.DURDURULDU) else None
        olaylar.append(Olay(
            kimlik=f"{c.nct}:{tur.name}:{gun.isoformat()}", tur=tur, ticker=c.ticker,
            satir=f"{c.ilac} · {c.hastalik}", ayrinti=ayrinti, tarih=gun, faz3=c.faz3,
            mikro=mikro.get(c.ticker, False), baglanti=f"https://clinicaltrials.gov/study/{c.nct}",
            etiket_ek=etiket_ek,
        ))

    for c in yeni:
        e = eski.get(c.nct)
        if e is None:
            # Görüntüde olmayan eski bir çalışma (yeni eşleme, evrene yeni giren şirket) "yeni" sayılmaz.
            if c.ilk_kayit == gun.isoformat():
                ekle(c, OlayTuru.YENI_FAZ3 if c.faz3 else OlayTuru.YENI_FAZ2, f"Yeni Faz {c.faz} çalışması kaydedildi")
            continue
        if c.durum in DURMUS and e.durum not in DURMUS:
            ekle(c, OlayTuru.DURDURULDU, f"Durum: {e.durum} → {c.durum}")
        elif c.durum == "COMPLETED" and e.durum != "COMPLETED":
            ekle(c, OlayTuru.TAMAMLANDI, "Çalışma tamamlandı olarak işaretlendi")
        if c.sonuc and not e.sonuc:
            ekle(c, OlayTuru.SONUC_GIRILDI, "Sonuçlar ClinicalTrials.gov'a girildi")
        eb, yb = bitis_tarihi(e), bitis_tarihi(c)
        if eb and yb and abs((yb - eb).days) >= KAYMA_ESIK_GUN:
            ekle(c, OlayTuru.TARIH_KAYDI, f"Bitiş {_ay(e)} → {_ay(c)}")
    return olaylar


def yaklasanlar(goruntu: Mapping[str, Calisma], bugun: date, gun: int = 60) -> List[Calisma]:
    son = bugun + timedelta(days=gun)
    secilen = []
    for c in goruntu.values():
        b = bitis_tarihi(c)
        if c.durum not in KAPALI and b and bugun <= b <= son:
            secilen.append((not c.faz3, b, c.ticker, c))
    return [x[-1] for x in sorted(secilen, key=lambda x: x[:3])]
