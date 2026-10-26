# src/opsi/strategies/covered_call.py
"""Covered Call: stock (≤$20) + OTM call sale; reuses CSP engine."""

from typing import Any

from ..params import DEFAULT_PARAMS
from ..scorer import core_score as _core_score
from ..types import CoreScore, EnrichedContract, Position, ScoreContext
from ._shared import stock_score_shared


def _filters(params: dict[str, Any] | None) -> dict[str, Any]:
    f = (params or {}).get("filters", DEFAULT_PARAMS["filters"])
    return f if isinstance(f, dict) else DEFAULT_PARAMS["filters"]


class CoveredCall:
    name = "covered_call"
    rights: tuple[str, ...] = ("C",)

    def universe_ok(
        self, price: float | None, is_etf: bool = False, params: dict[str, Any] | None = None
    ) -> bool:
        if price is None:
            return False
        return is_etf or price * 100 <= _filters(params)["capital_max"]

    def positions(
        self, contracts: list[EnrichedContract], price: float, params: dict[str, Any] | None = None
    ) -> list[Position]:
        f = _filters(params)
        out: list[Position] = []
        for e in contracts:
            if e["strike"] * 100 > f["cc_capital_max"]:  # filter out extreme strikes
                continue
            if not (f["dte_min"] <= e["dte"] <= f["dte_max"]):
                continue
            if not (f["call_lo"] <= e.get("delta", 0.5) <= f["call_hi"]):
                continue
            mid = e.get("mid", 0) or 0
            if mid <= 0:
                continue
            quoted = e.get("quoted", True)
            bid, ask = e.get("bid", 0) or 0, e.get("ask", 0) or 0
            if quoted and (ask - bid) / mid >= f["spread_max"]:
                continue
            if (e.get("volume", 0) or 0) < f["vol_min"] and (e.get("openInterest", 0) or 0) < f[
                "oi_min"
            ]:
                continue
            if e["strike"] <= price:  # OTM requirement: strike > stock
                continue
            out.append(
                {
                    "strategy": self.name,
                    "legs": [e],
                    "capital": price * 100,
                    "premium": mid,
                }
            )
        return out

    def score(
        self, pos: Position, ctx: ScoreContext, params: dict[str, Any] | None = None
    ) -> CoreScore:
        # prob_otm = 1 - |call delta| (core_score formula also works for call delta)
        return _core_score(pos["legs"][0], ctx, capital=pos["capital"], params=params)

    def stock_score(self, snapshot: dict[str, object]) -> float:
        return stock_score_shared(snapshot)

    def settle(self, legs: list[dict[str, float]], spot: float) -> float:
        leg = legs[0]
        s0, k, prem = leg.get("spot", spot), leg["strike"], leg["mid"]
        return (min(spot, k) - s0) * 100 + prem * 100
