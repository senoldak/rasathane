import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

KOK = Path(__file__).resolve().parents[2]
VERI = KOK / "rasathane" / "veri"
EK = KOK / "rasathane" / "evren_ek.csv"
CIKTI = KOK / "cikti"

# SEC erişim kuralı: User-Agent'ta gerçek bir iletişim e-postası zorunlu. GitHub noreply adresini
# SEC "beyansız araç" sayıp engelliyor; adres SEC_ILETISIM ayarından gelir.
SEC_UA_ONEK = "biOF Rasathane"


@dataclass
class Ayar:
    bot_token: Optional[str]
    sahip_id: Optional[str]
    hedef_sohbet: Optional[str]
    hedef_konu: Optional[int]
    gonderim_acik: bool
    sec_ua: Optional[str] = None


def hedef_ayristir(s: str) -> Tuple[str, Optional[int]]:
    sohbet, ayrac, konu = s.strip().rpartition(":")
    if not ayrac:
        return konu, None
    return sohbet, int(konu)


def ayar_oku(env: Mapping[str, str] = os.environ) -> Ayar:
    hedef = env.get("TELEGRAM_HEDEF") or ""
    sohbet, konu = hedef_ayristir(hedef) if hedef.strip() else (None, None)
    return Ayar(
        bot_token=env.get("TELEGRAM_BOT_TOKEN") or None,
        sahip_id=env.get("TELEGRAM_SAHIP_ID") or None,
        hedef_sohbet=sohbet,
        hedef_konu=konu,
        gonderim_acik=(env.get("RASATHANE_GONDERIM") or "").strip().lower() == "acik",
        sec_ua=f"{SEC_UA_ONEK} {env['SEC_ILETISIM'].strip()}" if (env.get("SEC_ILETISIM") or "").strip() else None,
    )
