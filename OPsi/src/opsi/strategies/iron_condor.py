# src/opsi/strategies/iron_condor.py
"""Iron Condor: bull-put-spread + bear-call-spread, same expiry, net credit > 0."""

from typing import Any

from ..scorer import core_score as _core_score
from ..types import CoreScore, EnrichedContract, Position, ScoreContext
from ._shared import stock_score_shared
from .spreads import call_spreads, put_spreads


class IronCondor:
    name = "iron_condor"
    rights: tuple[str, ...] = ("P", "C")

    def universe_ok(
        self, price: float | None, is_etf: bool = False, params: dict[str, Any] | None = None
    ) -> bool:
        # See BullPutSpread.universe_ok: collateral is width-bound, no price cap.
        return price is not None

    def positions(
        self, contracts: list[EnrichedContract], price: float, params: dict[str, Any] | None = None
    ) -> list[Position]:
        by_exp_put: dict[str, list[EnrichedContract]] = {}
        by_exp_call: dict[str, list[EnrichedContract]] = {}
        for e in contracts:
            # put/call split cannot be inferred from strike/price; use delta sign
            if (e.get("delta", 0) or 0) < 0:
                by_exp_put.setdefault(e["expiry"], []).append(e)
            else:
                by_exp_call.setdefault(e["expiry"], []).append(e)
        out: list[Position] = []
        for exp in set(by_exp_put) & set(by_exp_call):
            for ps, pl, pw in put_spreads(by_exp_put[exp], params=params):
                for cs, cl, cw in call_spreads(by_exp_call[exp], price, params=params):
                    credit = (ps["mid"] - pl["mid"]) + (cs["mid"] - cl["mid"])
                    max_loss = max(pw, cw) * 100 - credit * 100
                    if credit <= 0 or max_loss <= 0:
                        continue
                    # Iron rule: put-spread top < call-spread bottom (no overlap)
                    if pl["strike"] >= cs["strike"]:
                        continue
                    out.append(
                        {
                            "strategy": self.name,
                            "legs": [ps, pl, cs, cl],
                            "capital": max_loss,
                            "premium": credit,
                        }
                    )
        return out

    def score(
        self, pos: Position, ctx: ScoreContext, params: dict[str, Any] | None = None
    ) -> CoreScore:
        rep: EnrichedContract = {**pos["legs"][0], "mid": pos["premium"]}
        return _core_score(rep, ctx, capital=pos["capital"], params=params)

    def stock_score(self, snapshot: dict[str, object]) -> float:
        return stock_score_shared(snapshot)

    def settle(self, legs: list[dict[str, float]], spot: float) -> float:
        ps, pl, cs, cl = legs[0], legs[1], legs[2], legs[3]
        put_pnl = (ps["mid"] - pl["mid"]) * 100 - (
            max(ps["strike"] - spot, 0.0) - max(pl["strike"] - spot, 0.0)
        ) * 100
        call_pnl = (cs["mid"] - cl["mid"]) * 100 - (
            max(spot - cs["strike"], 0.0) - max(spot - cl["strike"], 0.0)
        ) * 100
        return put_pnl + call_pnl
