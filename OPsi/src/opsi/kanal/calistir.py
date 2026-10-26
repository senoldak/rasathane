# src/opsi/kanal/calistir.py
"""Günlük kanal akışı: işlem günü mü → evreni ölç → geçmişe yaz → kartları çiz → gönder.

Ayarlar ortamdan: TELEGRAM_BOT_TOKEN, TELEGRAM_HEDEF (@grup:konu), TELEGRAM_SAHIP_ID.
"""

import datetime
import logging
import os
from pathlib import Path
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

import numpy as np
from rasathane_ortak import kagit
from rasathane_ortak.tek_gonderim import Giden, GonderimKaydi

from .. import fetch
from .cizim import _AYLAR, FIKIR, SAYFA_SATIRI, csp_ciz, prim_ciz, sarsinti_ciz
from .evren import evren_oku
from .gecmis import (
    Kayit,
    gonderildi_isaretle,
    gonderildi_mi,
    gun_yaz,
    iv_seri,
    oku,
    onceki_gun,
)
from .grafik import AD as GRAFIK_AD
from .grafik import FiyatGecmisi, oynaklik_grafigi, oynaklik_secimi
from .kartlar import PrimKarti, SarsintiSatiri, asagi_yon_primi, csp_kartlari, iv_sarsintisi
from .olcum import CspAday, olc
from .telegram import gonder, sahibe_yaz

_NY = ZoneInfo("America/New_York")
_MIN_ORAN = 0.70
_PRIM_GUNLERI = {1, 3, 4}  # Salı, Perşembe, Cuma

log = logging.getLogger("opsi.kanal")


class Sonuc(TypedDict):
    durum: Literal[
        "islem_yok", "spy_yok", "zaten_gonderildi", "eksik_veri", "kart_yok", "kuru", "gonderildi"
    ]
    kart_sayisi: int
    okunan_oran: float


def _spy_gunleri() -> list[str]:
    return [d for d, _ in fetch.get_history("SPY", "1mo")]


def islem_gunu(simdi_utc: datetime.datetime, gunler: list[str] | None = None) -> str | None:
    """New York takvimindeki bugün SPY'nin son kapanış günüyse o tarih."""
    bugun = simdi_utc.astimezone(_NY).date().isoformat()
    gunler = _spy_gunleri() if gunler is None else gunler
    return bugun if gunler and gunler[-1] == bugun else None


def haftanin_ilki(tarih: str, gunler: list[str]) -> bool:
    d = datetime.date.fromisoformat(tarih)
    pazartesi = d - datetime.timedelta(days=d.weekday())
    return not any(pazartesi.isoformat() <= g < tarih for g in gunler)


def bugunun_kartlari(tarih: str, haftanin_ilk_islem_gunu: bool) -> list[str]:
    kartlar = ["sarsinti"]
    if haftanin_ilk_islem_gunu:
        kartlar.append("csp")
    if datetime.date.fromisoformat(tarih).weekday() in _PRIM_GUNLERI:
        kartlar.append("prim")
    return kartlar


def _hafta(tarih: str) -> str:
    d = datetime.date.fromisoformat(tarih)
    pzt = d - datetime.timedelta(days=d.weekday())
    cum = pzt + datetime.timedelta(days=4)
    if pzt.month == cum.month:
        return f"{pzt.day}–{cum.day} {_AYLAR[cum.month - 1]}"
    return f"{pzt.day} {_AYLAR[pzt.month - 1]} – {cum.day} {_AYLAR[cum.month - 1]}"


def _sahibe(metin: str) -> None:
    token, sahip = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_SAHIP_ID")
    if token and sahip:
        sahibe_yaz(token, sahip, metin)
    else:
        log.error("sahibe yazılamadı (token/sahip yok): %s", metin)


def calistir(
    kuru: bool,
    tarih: str | None = None,
    cikti: Path = Path("cikti"),
    simdi: datetime.datetime | None = None,
    veri: Path = Path("kanal_veri"),
    grafik_fiyat: FiyatGecmisi | None = None,
) -> Sonuc:
    simdi = simdi or datetime.datetime.now(datetime.UTC)
    if tarih is not None:
        datetime.date.fromisoformat(tarih)  # biçim YYYY-AA-GG değilse ValueError
        if len(tarih) != 10:
            raise ValueError(f"tarih YYYY-AA-GG olmalı: {tarih!r}")
    gunler = _spy_gunleri()
    if not gunler:
        _sahibe("OPsi kanal: Yahoo'dan SPY verisi alınamadı (engel ya da kesinti), gönderim yok.")
        return {"durum": "spy_yok", "kart_sayisi": 0, "okunan_oran": 0.0}
    if tarih is None:
        tarih = islem_gunu(simdi, gunler)
        if tarih is None:
            return {"durum": "islem_yok", "kart_sayisi": 0, "okunan_oran": 0.0}
    elif tarih != gunler[-1]:
        # Geçmiş günün opsiyon verisi yeniden çekilemez; bugünün verisi eski tarihe yazılmaz.
        raise ValueError(f"yalnız son seans ({gunler[-1]}) yeniden üretilebilir: {tarih}")
    gecmis_yolu, gonderilen_yolu = veri / "iv_gecmisi.csv", veri / "gonderilenler.json"
    if not kuru and gonderildi_mi(tarih, gonderilen_yolu):
        return {"durum": "zaten_gonderildi", "kart_sayisi": 0, "okunan_oran": 0.0}

    evren = evren_oku(veri / "evren.csv")
    adlar = {s["sembol"]: s["ad"] for s in evren}
    gecmis = [k for k in oku(gecmis_yolu) if k["tarih"] != tarih]
    bugun: list[Kayit] = []
    adaylar: list[CspAday] = []
    for satir in evren:
        try:
            o = olc(satir, tarih, iv_seri(gecmis, satir["sembol"], tarih), now=simdi)
        except Exception as e:
            log.warning("%s ölçülemedi: %s", satir["sembol"], e)
            o = None
        if o is None:
            continue
        bugun.append(o["kayit"])
        if o["csp"] is not None:
            adaylar.append(o["csp"])
    oran = len(bugun) / len(evren) if evren else 0.0
    if oran < _MIN_ORAN:
        _sahibe(f"OPsi kanal {tarih}: evrenin yalnız %{oran * 100:.0f}'i okunabildi, gönderim yok.")
        return {"durum": "eksik_veri", "kart_sayisi": 0, "okunan_oran": oran}
    gun_yaz(bugun, gecmis_yolu)

    kartlar: list[tuple[str, kagit.Kart]] = []
    sarsinti_satirlari: list[SarsintiSatiri] | None = None
    prim_karti: PrimKarti | None = None
    for kart in bugunun_kartlari(tarih, haftanin_ilki(tarih, gunler)):
        if kart == "sarsinti":
            once_t = onceki_gun(gecmis, tarih)
            if once_t is None:
                continue
            bosluk = int(np.busday_count(once_t, tarih))
            satirlar = iv_sarsintisi(
                bugun, [k for k in gecmis if k["tarih"] == once_t], adlar, bosluk
            )
            if satirlar:
                sarsinti_satirlari = satirlar
                kartlar.append(("sarsinti", sarsinti_ciz(satirlar, tarih, once_t, len(bugun))))
        elif kart == "csp":
            for ck in csp_kartlari(adaylar, bugun, gecmis, adlar):
                kartlar.append((f"csp:{ck['bant']}", csp_ciz(ck, tarih, _hafta(tarih))))
        elif kart == "prim":
            pk = asagi_yon_primi(bugun, adlar)
            if pk:
                prim_karti = pk
                kartlar.append(("prim", prim_ciz(pk, tarih, len(bugun))))

    gidenler: list[Giden] = []
    for anahtar, k in kartlar:
        for sf in kagit.ciz(k, sayfa_basina=SAYFA_SATIRI):
            aciklama = kagit.mesaj_metni(FIKIR, k.ad, k.tarih, sf.no, sf.toplam)
            gidenler.append(Giden(anahtar, sf.no, sf.png, aciklama))

    secim = oynaklik_secimi(prim_karti, sarsinti_satirlari)
    if grafik_fiyat and secim:
        sembol, gerekce = secim
        try:
            kayit = next(k for k in bugun if k["sembol"] == sembol)
            png = kagit.grafik_ciz(
                oynaklik_grafigi(
                    sembol,
                    adlar.get(sembol, sembol),
                    gerekce,
                    tarih,
                    kayit,
                    grafik_fiyat(sembol, "6mo"),
                )
            )
            gidenler.append(
                Giden(
                    "grafik",
                    1,
                    png,
                    kagit.mesaj_metni(
                        FIKIR, GRAFIK_AD, kagit.tarih_metni(datetime.date.fromisoformat(tarih))
                    ),
                )
            )
        except Exception as e:  # grafik yalnız ektir; diğer kartlar yine gider
            log.warning("Oynaklık grafiği çizilemedi: %s", e)
            if not kuru:
                _sahibe(f"OPsi kanal {tarih}: Oynaklık grafiği atlandı: {e}")

    cikti.mkdir(parents=True, exist_ok=True)
    for i, g in enumerate(gidenler):
        (cikti / f"{tarih}_{i}.png").write_bytes(g.png)
    if not gidenler:
        return {"durum": "kart_yok", "kart_sayisi": 0, "okunan_oran": oran}
    if kuru:
        return {"durum": "kuru", "kart_sayisi": len(gidenler), "okunan_oran": oran}

    try:
        gonder(
            os.environ["TELEGRAM_BOT_TOKEN"],
            os.environ["TELEGRAM_HEDEF"],
            tarih,
            gidenler,
            GonderimKaydi(veri / "gonderilen_kartlar.csv"),
        )
    except Exception as e:
        _sahibe(f"OPsi kanal {tarih}: gönderim başarısız (giden kartlar kaydedildi): {e}")
        raise
    gonderildi_isaretle(tarih, gonderilen_yolu)
    return {"durum": "gonderildi", "kart_sayisi": len(gidenler), "okunan_oran": oran}
