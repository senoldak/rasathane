# src/opsi/strategies/base.py
"""Strategy protocol: each strategy provides universe filter + position generation + scoring."""

from typing import Any, Protocol

from ..types import CoreScore, EnrichedContract, Position, ScoreContext


class Strategy(Protocol):
    name: str
    rights: tuple[str, ...]

    def universe_ok(
        self, price: float | None, is_etf: bool = False, params: dict[str, Any] | None = None
    ) -> bool:
        """Does the underlying price fit the strategy capital?"""
        ...

    def positions(
        self,
        contracts: list[EnrichedContract],
        price: float,
        params: dict[str, Any] | None = None,
    ) -> list[Position]:
        """Builds positions from enriched contracts.

        Note: the earnings <7d gate lives in scan.py run_full_scan; plugin
        filters deliberately exclude it (see csp.py).
        """
        ...

    def score(
        self, pos: Position, ctx: ScoreContext, params: dict[str, Any] | None = None
    ) -> CoreScore:
        """Scores a position with a 0-100 core score."""
        ...

    def stock_score(self, snapshot: dict[str, object]) -> float:
        """Underlying quality 0-100 (snapshot: close, put_volume, put_oi, spread_sample, stale_flag, earnings_days)."""
        ...

    def settle(self, legs: list[dict[str, float]], spot: float) -> float:
        """Expiry P&L ($) — legs: [{strike, mid}], spot: underlying price."""
        ...
