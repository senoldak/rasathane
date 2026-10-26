# src/opsi/strategies/spreads.py
"""Shared spread matching: same expiry, short/long leg selection."""

from typing import Any

from ..params import DEFAULT_PARAMS
from ..types import EnrichedContract


def _filters(params: dict[str, Any] | None) -> dict[str, Any]:
    f = (params or {}).get("filters", DEFAULT_PARAMS["filters"])
    return f if isinstance(f, dict) else DEFAULT_PARAMS["filters"]


def _valid_leg(
    e: EnrichedContract,
    dte_min: int | None = None,
    dte_max: int | None = None,
    params: dict[str, Any] | None = None,
) -> bool:
    f = _filters(params)
    lo = dte_min if dte_min is not None else f["dte_min"]
    hi = dte_max if dte_max is not None else f["dte_max"]
    mid = e.get("mid", 0) or 0
    if mid <= 0:
        return False
    if not (lo <= e["dte"] <= hi):
        return False
    quoted = e.get("quoted", True)
    bid, ask = e.get("bid", 0) or 0, e.get("ask", 0) or 0
    if quoted and (ask - bid) / mid >= f["spread_max"]:
        return False
    return not (
        (e.get("volume", 0) or 0) < f["vol_min"] and (e.get("openInterest", 0) or 0) < f["oi_min"]
    )


def put_spreads(
    contracts: list[EnrichedContract],
    short_lo: float | None = None,
    short_hi: float | None = None,
    max_width: float | None = None,
    max_pairs_per_short: int | None = None,
    params: dict[str, Any] | None = None,
) -> list[tuple[EnrichedContract, EnrichedContract, float]]:
    """Short (in delta range) + long (lower strike) put pairs."""
    f = _filters(params)
    short_lo = f["put_lo"] if short_lo is None else short_lo
    short_hi = f["put_hi"] if short_hi is None else short_hi
    max_width = f["width_max"] if max_width is None else max_width
    max_pairs_per_short = f["pairs_max"] if max_pairs_per_short is None else max_pairs_per_short
    by_exp: dict[str, list[EnrichedContract]] = {}
    for e in contracts:
        by_exp.setdefault(e["expiry"], []).append(e)
    out: list[tuple[EnrichedContract, EnrichedContract, float]] = []
    for legs in by_exp.values():
        shorts = [
            e
            for e in legs
            if short_lo <= e.get("delta", -0.5) <= short_hi and _valid_leg(e, params=params)
        ]
        for short in shorts:
            longs = sorted(
                (
                    e
                    for e in legs
                    if e["strike"] < short["strike"]
                    and 0 < short["strike"] - e["strike"] <= max_width
                    and _valid_leg(e, params=params)
                ),
                key=lambda e: short["strike"] - e["strike"],
                reverse=True,
            )[:max_pairs_per_short]
            for long in longs:
                credit = short["mid"] - long["mid"]
                if credit > 0:
                    out.append((short, long, short["strike"] - long["strike"]))
    return out


def call_spreads(
    contracts: list[EnrichedContract],
    price: float,
    short_lo: float | None = None,
    short_hi: float | None = None,
    max_width: float | None = None,
    max_pairs_per_short: int | None = None,
    params: dict[str, Any] | None = None,
) -> list[tuple[EnrichedContract, EnrichedContract, float]]:
    """Short (in delta range, OTM) + long (higher strike) call pairs."""
    f = _filters(params)
    short_lo = f["call_lo"] if short_lo is None else short_lo
    short_hi = f["call_hi"] if short_hi is None else short_hi
    max_width = f["width_max"] if max_width is None else max_width
    max_pairs_per_short = f["pairs_max"] if max_pairs_per_short is None else max_pairs_per_short
    by_exp: dict[str, list[EnrichedContract]] = {}
    for e in contracts:
        by_exp.setdefault(e["expiry"], []).append(e)
    out: list[tuple[EnrichedContract, EnrichedContract, float]] = []
    for legs in by_exp.values():
        shorts = [
            e
            for e in legs
            if e["strike"] > price
            and short_lo <= e.get("delta", 0.5) <= short_hi
            and _valid_leg(e, params=params)
        ]
        for short in shorts:
            longs = sorted(
                (
                    e
                    for e in legs
                    if e["strike"] > short["strike"]
                    and 0 < e["strike"] - short["strike"] <= max_width
                    and _valid_leg(e, params=params)
                ),
                key=lambda e: e["strike"] - short["strike"],
                reverse=True,
            )[:max_pairs_per_short]
            for long in longs:
                credit = short["mid"] - long["mid"]
                if credit > 0:
                    out.append((short, long, long["strike"] - short["strike"]))
    return out
