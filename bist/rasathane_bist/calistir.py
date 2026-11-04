"""Son VİOP bültenini bulup site JSON'larını yazar. Telegram kartı yoktur."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .bulten import PaySatiri, pay_bulteni_oku
from .gecmis import Gecmis, gecmis_oku, gecmis_yaz, geri_doldur, gun_ozeti
from .indir import Indirici, dosya_al, pay_bulteni_url
from .site_aktar import aktar
from .site_ek import ek_sayfalar
from .viop import ViopSatiri, viop_bulteni_oku, viop_bulteni_url
from .yahoo import kapanislar

log = logging.getLogger("viop")

# Türkiye UTC+3 (yaz saati yok): sabit ofset, zoneinfo/tzdata bağımlılığı yok.
ISTANBUL = timezone(timedelta(hours=3))
GERI_GUN = 7
ENDEKS_YAHOO = {"XU030": "XU030.IS"}
GECMIS_YOLU = Path(__file__).resolve().parents[1] / "veri" / "viop-gunluk.json"


def http_indir(url: str) -> tuple[int, bytes]:
    """Ağ isteği; HTTP hatalarında durum kodunu döndürür (404 dahil, istisna fırlatmaz)."""
    istek = urllib.request.Request(url, headers={"User-Agent": "rasathane-bist/0.1"})
    try:
        with urllib.request.urlopen(istek, timeout=30) as yanit:
            return int(yanit.status), bytes(yanit.read())
    except urllib.error.HTTPError as hata:
        return hata.code, b""


def son_bulten(
    bugun: date, indir: Indirici, geri: int = GERI_GUN
) -> tuple[date, list[ViopSatiri]] | None:
    """`bugun`den geriye en yeni yayımlanmış bülten. Hafta sonu ve tatiller 404 döner."""
    for n in range(geri):
        gun = bugun - timedelta(days=n)
        bayt = dosya_al(indir, viop_bulteni_url(gun))
        if bayt is not None:
            return viop_bulteni_oku(bayt)
    return None


def pay_bulteni_al(gun: date, indir: Indirici) -> list[PaySatiri]:
    """Günün pay bülteni; yoksa boş liste (varant ve spot için yardımcı veri)."""
    bayt = dosya_al(indir, pay_bulteni_url(gun))
    if bayt is None:
        return []
    _, satirlar = pay_bulteni_oku(bayt)
    return satirlar


def spot_fiyatlari(pay: list[PaySatiri], gun: date, endeks: bool) -> dict[str, float]:
    """Dayanak kodu -> kapanış. Hisseler pay bülteninden, endeks Yahoo'dan (yoksa atlanır)."""
    spot = {
        s.kod[:-2]: s.kapanis
        for s in pay
        if s.tip == "MSPOTEQT" and s.kod.endswith(".E") and s.kapanis > 0
    }
    if not endeks:
        return spot
    try:
        for dayanak, sembol in ENDEKS_YAHOO.items():
            fiyat = kapanislar([sembol], gun).get(sembol)
            if fiyat:
                spot[dayanak] = fiyat
    except Exception as hata:  # noqa: BLE001 - endeks yoksa vadeli ve pay sayfaları yine yazılır
        log.warning("endeks kapanışı alınamadı: %s", hata)
    return spot


def calistir(
    kok: Path,
    bugun: date | None = None,
    indir: Indirici = http_indir,
    simdi: datetime | None = None,
    faiz: float | None = None,
    gecmis_yolu: Path | None = None,
    endeks: bool = True,
) -> list[Path] | None:
    """Bülteni bulur, geçmişi biriktirir ve `kok/viop/` altına yazar. Bülten yoksa `None`.

    `faiz`: risksiz faiz, ondalık (0,358 = %35,8). Verilmezse etkin kaldıraç hesaplanmaz.
    `gecmis_yolu`: birikim dosyası; `None` ise geçmiş diske yazılmaz. `endeks`: Yahoo'dan endeks kapanışı.
    """
    hedef = bugun or datetime.now(ISTANBUL).date()
    sonuc = son_bulten(hedef, indir)
    if sonuc is None:
        log.warning("VİOP bülteni bulunamadı (%s ve önceki %d gün)", hedef, GERI_GUN - 1)
        return None
    gun, satirlar = sonuc
    log.info("VİOP bülteni %s: %d satır", gun, len(satirlar))

    gecmis: Gecmis = gecmis_oku(gecmis_yolu) if gecmis_yolu else {}
    eklenen = geri_doldur(gecmis, gun, indir)
    gecmis[gun.isoformat()] = gun_ozeti(satirlar)
    if gecmis_yolu:
        gecmis_yaz(gecmis_yolu, gecmis)
    log.info("VİOP geçmişi: %d yeni gün, toplam %d", eklenen, len(gecmis))

    simdi_ = simdi or datetime.now(timezone.utc)
    pay = pay_bulteni_al(gun, indir)
    spot = spot_fiyatlari(pay, gun, endeks)
    yollar = aktar(kok, gun, satirlar, simdi_)
    yollar += ek_sayfalar(kok, gun, satirlar, pay, gecmis, spot, faiz, simdi_)
    return yollar
