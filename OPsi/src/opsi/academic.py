# src/opsi/academic.py
"""Scoring engine Layer-3: independent academic multipliers (on/off flags)."""

from typing import Any

from .params import DEFAULT_PARAMS
from .types import AcademicFlags, CoreScore, EnrichedContract, FinalScore


def kelly_fraction(edge: float, odds: float) -> float:
    """Kelly position size; capped at 25%, 0 on invalid odds."""
    if odds <= 0:
        return 0.0
    f = edge / odds
    return max(0.0, min(0.25, f))


def apply_academic(
    base: CoreScore,
    e: EnrichedContract,
    flags: AcademicFlags,
    params: dict[str, Any] | None = None,
) -> FinalScore:
    """Applies bounded multiplier to core score, returns reasons in notes."""
    a = (params or {}).get("academic", DEFAULT_PARAMS["academic"])
    mult, notes = 1.0, []
    if flags.get("skew"):
        iv = e.get("iv", 0.3)
        if iv > a["skew_hi"]:
            mult *= a["m_skew_hi"]
            notes.append("skew: iv cok yuksek, kuyruk riski")
        elif iv > a["skew_lo"]:
            mult *= a["m_skew_lo"]
            notes.append("skew: prim cekici")
    if flags.get("term") and e.get("dte", 20) < a["term_dte"]:
        mult *= a["m_term"]
        notes.append("term: kisa vade")
    if flags.get("jump") and e.get("earnings_days") is not None and e["earnings_days"] < a["jump_days"]:  # type: ignore[typeddict-item]
        mult *= a["m_jump"]
        notes.append("jump: earnings yakin")
    mult = max(a["clamp_lo"], min(a["clamp_hi"], mult))
    final = max(0.0, min(100.0, base["score"] * mult))
    return {**base, "adj": mult, "final": final, "notes": notes}
