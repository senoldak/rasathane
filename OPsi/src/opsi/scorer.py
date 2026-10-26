# src/opsi/scorer.py
"""Scoring engine Layer-1 (filter) + Layer-2 (core score)."""

from typing import Any

from .params import DEFAULT_PARAMS, norm_weights
from .types import CoreScore, EnrichedContract, ScoreContext


def _filters(params: dict[str, Any] | None) -> dict[str, Any]:
    f = (params or {}).get("filters", DEFAULT_PARAMS["filters"])
    return f if isinstance(f, dict) else DEFAULT_PARAMS["filters"]


def passes_filters(
    e: EnrichedContract,
    price: float,
    earnings_days: int | None = None,
    params: dict[str, Any] | None = None,
) -> bool:
    """Layer-1: capital/DTE/delta/liquidity/earnings filter.

    Spread check is skipped for unquoted (quoted=False) contracts;
    volume/OI threshold always applies.

    The price parameter is kept for the plan interface (capital is checked via strike).
    """
    f = _filters(params)
    if e["strike"] * 100 > f["capital_max"]:
        return False
    if not (f["dte_min"] <= e["dte"] <= f["dte_max"]):
        return False
    if not (f["put_lo"] <= e.get("delta", -0.5) <= f["put_hi"]):
        return False
    bid, ask = e.get("bid", 0) or 0, e.get("ask", 0) or 0
    mid = e.get("mid", 0.5 * (bid + ask)) or 0
    if mid <= 0:
        return False
    quoted = e.get("quoted", bid > 0 and ask >= bid)
    if quoted and (ask - bid) / mid >= f["spread_max"]:
        return False
    if (e.get("volume", 0) or 0) < f["vol_min"] and (e.get("openInterest", 0) or 0) < f["oi_min"]:
        return False
    return not (earnings_days is not None and earnings_days < f["earnings_days"])


def _norm(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def core_score(
    e: EnrichedContract,
    ctx: ScoreContext,
    capital: float | None = None,
    params: dict[str, Any] | None = None,
) -> CoreScore:
    """Layer-2: 0-100 core score + components.

    Uses strike*100 (CSP assumption) when capital is omitted.
    Uses ctx["params"] when params is omitted, else defaults.
    """
    p = params if params is not None else ctx.get("params")
    f = _filters(p)
    w = norm_weights(p)
    w_all = (p or {}).get("weights", DEFAULT_PARAMS["weights"])
    ret_hi = max(0.05, float(w_all.get("ret_norm_hi", 0.6)))
    mid = e.get("mid", 0.5 * (e["bid"] + e["ask"])) or 0
    cap = capital if capital is not None else e["strike"] * 100
    ret_ann = ((mid * 100.0) / cap) * (365.0 / max(1, e["dte"])) if cap > 0 else 0.0
    prob_otm = 1.0 - abs(e.get("delta", -0.2))
    quoted = e.get("quoted", True)
    if quoted and mid:
        spread_term = max(0.0, 1.0 - ((e["ask"] - e["bid"]) / mid) * f["spread_penalty"])
    else:
        spread_term = 0.5  # no quote: spread neutral, volume/OI decides
    liq = 0.5 * spread_term + 0.5 * _norm(
        min(e.get("volume", 0), 2000) / 2000 + min(e.get("openInterest", 0), 10000) / 10000,
        0,
        1,
    )
    liq = max(0.0, min(1.0, liq))
    hist = ctx.get("iv_history") or []
    if len(hist) >= 10:
        iv_rank = sum(1 for v in hist if v <= e.get("iv", 0.3)) / len(hist)
    else:
        iv_rank = _norm(e.get("iv", 0.3), ctx.get("iv_min", 0.1), ctx.get("iv_max", 0.8))
    trend = float(ctx.get("trend", 0.5))
    score = 100 * (
        w["ret"] * _norm(ret_ann, 0, ret_hi)
        + w["otm"] * prob_otm
        + w["liq"] * liq
        + w["iv"] * iv_rank
        + w["trend"] * trend
    )
    return {
        "score": score,
        "ret_ann": ret_ann,
        "prob_otm": prob_otm,
        "liq": liq,
        "iv_rank": iv_rank,
        "trend": trend,
    }
