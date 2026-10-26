import re
from typing import Optional, Tuple

from bioseeder.rasathane.olay import OlayTuru

# Kurallar bilerek dar: yanlış "onay/ret/sonuç" yayımlamak, bir olayı kaçırmaktan pahalı.
# FDA kararları yalnız başlık bölgesinde (ilk 200 karakter) aranır.
_FDA = re.compile(r"\bfda\b")
_ONAY = re.compile(r"\bapprov(es|ed|al)\b")
_ONAY_DEGIL = re.compile(
    r"anticipat|expect|pdufa|accept(s|ed|ance)?\b.{0,40}(application|submission|filing)"
    r"|submit|seek|potential|planned|\bwill\b|advisory|committee|\bvotes?\b|\bind\b|investigational"
    r"|initiat|clearance"
)
_RET = re.compile(r"(receiv\w*|issued|issues)\b.{0,60}complete response letter|complete response letter\b.{0,30}from")
_RET_DEGIL = re.compile(r"resubmi|following|addressing|after")
# Bilanço ve kurumsal güncelleme bültenleri faz sonucu sayılmaz.
_FINANSAL = re.compile(r"financial results|\bquarter\b|fiscal|corporate update|business update|annual report")
_FAZ3 = r"phase\s*(?:2b/3|2/3|ii/iii|3|iii)\b"
_FAZ2 = r"phase\s*(?:1/2|i/ii|2a|2b|2|ii)\b"
_SONUC = r"(?:topline|top-line|primary endpoint|results|data from|data|readout)"


def _yakin(faz: str, metin: str) -> bool:
    """Faz ifadesi ile sonuç ifadesi 80 karakter içinde (herhangi bir sırada) geçiyor mu?"""
    return bool(re.search(rf"{faz}.{{0,80}}{_SONUC}|{_SONUC}.{{0,80}}{faz}", metin))


def siniflandir(metin: str) -> Optional[Tuple[OlayTuru, bool]]:
    baslik = metin[:200].lower()
    bas = metin[:600].lower()
    onay_basligi = bool(_FDA.search(baslik) and _ONAY.search(baslik))
    if _RET.search(baslik) and not _RET_DEGIL.search(baslik) and not onay_basligi:
        return OlayTuru.FDA_RET, False
    if onay_basligi and not _ONAY_DEGIL.search(baslik):
        return OlayTuru.FDA_ONAY, False
    if _FINANSAL.search(baslik):
        return None
    if _yakin(_FAZ3, bas):
        return OlayTuru.FAZ3_SONUC, True
    if _yakin(_FAZ2, bas):
        return OlayTuru.FAZ2_SONUC, False
    return None
