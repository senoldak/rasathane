"""Hangi beyanların karta gireceği: günlük ve haftalık seçim kuralları."""
import datetime
from collections import Counter
from dataclasses import dataclass, field

from capitolseeder.kanal.model import Beyan, hisse_mi


def gunluk(yeniler: list[Beyan], adet: int = 8, uye_basi: int = 3) -> list[Beyan]:
    adaylar = sorted(
        (b for b in yeniler if hisse_mi(b)),
        key=lambda b: (-b.tutar_alt, -b.islem_tarihi.toordinal()),
    )
    sayac: Counter[str] = Counter()
    secilen: list[Beyan] = []
    for b in adaylar:
        if sayac[b.uye] >= uye_basi:
            continue
        sayac[b.uye] += 1
        secilen.append(b)
        if len(secilen) == adet:
            break
    return secilen


@dataclass
class HisseOzeti:
    ticker: str
    varlik: str
    alan_uyeler: set[str] = field(default_factory=set)
    satan_uyeler: set[str] = field(default_factory=set)
    partiler: Counter[str] = field(default_factory=Counter)
    alan_partiler: set[str] = field(default_factory=set)
    tutar_alt: int = 0
    tutar_ust: int = 0

    @property
    def uye_sayisi(self) -> int:
        return len(self.alan_uyeler | self.satan_uyeler)

    @property
    def iki_parti_alim(self) -> bool:
        return {"D", "R"} <= self.alan_partiler


def haftalik(
    beyanlar: list[Beyan],
    pazartesi: datetime.date,
    adet: int = 8,
    gun_sayisi: int = 5,
    alan: str = "ilk_gorulme",
) -> list[HisseOzeti]:
    """`alan`: pencere için bakılan tarih ("ilk_gorulme" ya da önizlemede "beyan_tarihi")."""
    gunler = {(pazartesi + datetime.timedelta(days=i)).isoformat() for i in range(gun_sayisi)}
    ozetler: dict[str, HisseOzeti] = {}
    uye_partisi: dict[tuple[str, str], str] = {}
    for b in beyanlar:
        deger = getattr(b, alan)
        if isinstance(deger, datetime.date):
            deger = deger.isoformat()
        if deger not in gunler or not hisse_mi(b):
            continue
        o = ozetler.setdefault(b.ticker, HisseOzeti(ticker=b.ticker, varlik=b.varlik))
        if b.yon == "Alış":
            o.alan_uyeler.add(b.uye)
            o.alan_partiler.add(b.parti)
        else:
            o.satan_uyeler.add(b.uye)
        uye_partisi[(b.ticker, b.uye)] = b.parti
        o.tutar_alt += b.tutar_alt
        o.tutar_ust += b.tutar_ust
    for (ticker, _), parti in uye_partisi.items():
        ozetler[ticker].partiler[parti] += 1
    if len(ozetler) < 3:
        return []
    return sorted(ozetler.values(), key=lambda o: (-o.uye_sayisi, -o.tutar_alt))[:adet]


def ayin_ilk_cumasi(d: datetime.date) -> bool:
    return d.weekday() == 4 and d.day <= 7
