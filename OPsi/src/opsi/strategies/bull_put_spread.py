# src/opsi/strategies/bull_put_spread.py
"""Bull Put Spread: high-strike short put + low-strike long put, net credit > 0."""

from typing import Any

from ..scorer import core_score as _core_score
from ..types import CoreScore, EnrichedContract, Position, ScoreContext
from ._shared import stock_score_shared
from .spreads import put_spreads


class BullPutSpread:
    name = "bull_put_spread"
    rights: tuple[str, ...] = ("P",)

    def universe_ok(
        self, price: float | None, is_etf: bool = False, params: dict[str, Any] | None = None
    ) -> bool:
        # Capital discipline comes from width (width_max → ~$500 collateral);
        # stock price does not set spread collateral, so no price cap.
        return price is not None

    def positions(
        self, contracts: list[EnrichedContract], price: float, params: dict[str, Any] | None = None
    ) -> list[Position]:
        out: list[Position] = []
        for short, long, width in put_spreads(contracts, params=params):
            credit = short["mid"] - long["mid"]
            max_loss = width * 100 - credit * 100
            if max_loss <= 0:
                continue
            out.append(
                {
                    "strategy": self.name,
                    "legs": [short, long],
                    "capital": max_loss,
                    "premium": credit,
                }
            )
        return out

    def score(
        self, pos: Position, ctx: ScoreContext, params: dict[str, Any] | None = None
    ) -> CoreScore:
        short = pos["legs"][0]
        rep: EnrichedContract = {**short, "mid": pos["premium"]}
        return _core_score(rep, ctx, capital=pos["capital"], params=params)

    def stock_score(self, snapshot: dict[str, object]) -> float:
        return stock_score_shared(snapshot)

    def settle(self, legs: list[dict[str, float]], spot: float) -> float:
        short, long = legs[0], legs[1]
        credit = short["mid"] - long["mid"]
        return (
            credit * 100
            - max(short["strike"] - spot, 0.0) * 100
            + max(long["strike"] - spot, 0.0) * 100
        )
