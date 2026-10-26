# src/opsi/kanal/olcum.py
"""Bir evren sembolünün günlük ölçümü: kapanış, IV30, skew, bilanço ve en iyi CSP adayı."""

import copy
import datetime
from typing import Any, TypedDict

import yfinance as yf

from .. import fetch
from ..params import DEFAULT_PARAMS
from ..pricer import enrich
from ..strategies.csp import CashSecuredPut
from ..types import RawContract, ScoreContext
from .evren import EvrenSatiri
from .gecmis import Kayit
from .iv import atm_iv, gecerli_noktalar, iv30, skew25

KANAL_PARAMS: dict[str, dict[str, Any]] = copy.deepcopy(DEFAULT_PARAMS)
KANAL_PARAMS["filters"].update({"dte_min": 20, "dte_max": 45, "capital_max": 15000.0})

_MAKS_VADE = 5


class CspAday(TypedDict):
    sembol: str
    skor: float
    strike: float
    dte: int
    sermaye: float


class Olcum(TypedDict):
    kayit: Kayit
    csp: CspAday | None


def vade_sec(vadeler: list[str], now: datetime.datetime | None = None) -> list[str]:
    """IV30 ve CSP için yeterli az sayıda vade: 30'u çevreleyen ikisi + 20–45'te 30'a yakınlar."""
    bugun = (now or datetime.datetime.now(datetime.UTC)).date()
    dte: dict[str, int] = {}
    for v in vadeler:
        try:
            d = (datetime.date.fromisoformat(v) - bugun).days
        except ValueError:
            continue
        if 7 <= d <= 90:
            dte[v] = d
    secilen: list[str] = []
    alt = [v for v in dte if dte[v] <= 30]
    ust = [v for v in dte if dte[v] >= 30]
    if alt:
        secilen.append(max(alt, key=lambda v: dte[v]))
    if ust:
        secilen.append(min(ust, key=lambda v: dte[v]))
    for v in sorted((v for v in dte if 20 <= dte[v] <= 45), key=lambda v: abs(dte[v] - 30)):
        if len(set(secilen)) >= _MAKS_VADE:
            break
        secilen.append(v)
    return sorted(set(secilen), key=lambda v: dte[v])


def _put_zinciri(sembol: str, now: datetime.datetime | None = None) -> list[RawContract]:
    fetch._throttle()
    out: list[RawContract] = []
    try:
        t = yf.Ticker(sembol)
        vadeler = vade_sec(list(t.options or []), now=now)
    except Exception:
        return out
    for exp in vadeler:
        try:
            puts = t.option_chain(exp).puts
        except Exception:
            continue
        for _, r in puts.iterrows():
            out.append(
                {
                    "symbol": sembol,
                    "expiry": exp,
                    "strike": float(r["strike"]),
                    "bid": fetch._to_float(r.get("bid", 0)),
                    "ask": fetch._to_float(r.get("ask", 0)),
                    "lastPrice": fetch._to_float(r.get("lastPrice", 0)),
                    "volume": fetch._to_int(r.get("volume", 0)),
                    "openInterest": fetch._to_int(r.get("openInterest", 0)),
                }
            )
    return out


def _csp_adayi(
    sembol: str,
    chain: list[RawContract],
    gecerli: set[tuple[str, float]],
    spot: float,
    iv_gecmisi: list[float],
    now: datetime.datetime | None,
) -> CspAday | None:
    strat = CashSecuredPut()
    zengin = [enrich(c, spot, now=now) for c in chain if (c["expiry"], c["strike"]) in gecerli]
    ctx: ScoreContext = {"iv_history": iv_gecmisi, "trend": 0.5, "params": KANAL_PARAMS}
    en_iyi: CspAday | None = None
    for pos in strat.positions(zengin, spot, params=KANAL_PARAMS):
        skor = strat.score(pos, ctx, params=KANAL_PARAMS)["score"]
        bacak = pos["legs"][0]
        if en_iyi is None or skor > en_iyi["skor"]:
            en_iyi = {
                "sembol": sembol,
                "skor": skor,
                "strike": bacak["strike"],
                "dte": bacak["dte"],
                "sermaye": pos["capital"],
            }
    return en_iyi


def olc(
    satir: EvrenSatiri,
    tarih: str,
    iv_gecmisi: list[float],
    now: datetime.datetime | None = None,
) -> Olcum | None:
    """Okunamayan sembol (fiyat ya da IV30 yok) için None."""
    sembol = satir["sembol"]
    spot = fetch.get_price(sembol)
    if spot is None or spot <= 0:
        return None
    chain = _put_zinciri(sembol, now=now)
    noktalar = gecerli_noktalar(chain, spot, now=now)
    v30 = iv30(noktalar, spot)
    if v30 is None:
        return None
    yakin = [n for n in noktalar if 20 <= n["dte"] <= 45]
    atm = (
        atm_iv(noktalar, min(yakin, key=lambda n: abs(n["dte"] - 30))["expiry"], spot)
        if yakin
        else None
    )
    kayit: Kayit = {
        "tarih": tarih,
        "sembol": sembol,
        "kapanis": spot,
        "iv30": v30,
        "skew25": skew25(noktalar, spot),
        "atm_iv": atm,
        "bilanco_gun": fetch.get_earnings_days(sembol),
    }
    csp = None
    bilanco = kayit["bilanco_gun"]
    yakin_bilanco = bilanco is not None and 0 <= bilanco < KANAL_PARAMS["filters"]["earnings_days"]
    if not satir["etf"] and not yakin_bilanco:
        gecerli = {(n["expiry"], n["strike"]) for n in yakin}
        csp = _csp_adayi(sembol, chain, gecerli, spot, iv_gecmisi, now)
    return {"kayit": kayit, "csp": csp}
