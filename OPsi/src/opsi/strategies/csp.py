# src/opsi/strategies/csp.py
"""Cash-Secured Put: exact wrapper of current Layer-1 + Layer-2 behavior."""

from typing import Any

from ..params import DEFAULT_PARAMS
from ..scorer import core_score as _core_score
from ..scorer import passes_filters
from ..types import CoreScore, EnrichedContract, Position, ScoreContext
from ._shared import stock_score_shared


def _filters(params: dict[str, Any] | None) -> dict[str, Any]:
    f = (params or {}).get("filters", DEFAULT_PARAMS["filters"])
    return f if isinstance(f, dict) else DEFAULT_PARAMS["filters"]


class CashSecuredPut:
    name = "csp"
    rights: tuple[str, ...] = ("P",)

    def universe_ok(
        self, price: float | None, is_etf: bool = False, params: dict[str, Any] | None = None
    ) -> bool:
        if price is None:
            return False
        return is_etf or price < _filters(params)["csp_price_max"]

    def positions(
        self, contracts: list[EnrichedContract], price: float, params: dict[str, Any] | None = None
    ) -> list[Position]:
        """Builds CSP positions from put candidates via Layer-1.

        Note: the earnings <7d gate lives in scan.py run_full_scan; the
        plugin filter (passes_filters) deliberately excludes it.
        """
        out: list[Position] = []
        for e in contracts:
            if not passes_filters(e, price, params=params):
                continue
            out.append(
                {
                    "strategy": self.name,
                    "legs": [e],
                    "capital": e["strike"] * 100,
                    "premium": e["mid"],
                }
            )
        return out

    def score(
        self, pos: Position, ctx: ScoreContext, params: dict[str, Any] | None = None
    ) -> CoreScore:
        return _core_score(pos["legs"][0], ctx, params=params)

    def stock_score(self, snapshot: dict[str, object]) -> float:
        return stock_score_shared(snapshot)

    def settle(self, legs: list[dict[str, float]], spot: float) -> float:
        k, prem = legs[0]["strike"], legs[0]["mid"]
        return prem * 100 - max(k - spot, 0.0) * 100
