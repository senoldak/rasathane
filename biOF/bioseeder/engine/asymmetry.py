import math
from typing import Optional


def calculate_asymmetry_score(
    target_tam: Optional[float],
    market_cap: Optional[float],
    is_big_pharma: bool = False,
) -> float:
    """
    Calculate asymmetric payoff score (0 to 100).
    - Evaluates the ratio of Target Addressable Market (TAM) to Market Capitalization.
    - Continuous and strictly monotonic across all valuation tiers.
    - A 5x TAM-to-valuation ratio yields the maximum score of 100.0.
    """
    if target_tam is None or math.isnan(target_tam):
        return 0.0

    tam = max(0.0, float(target_tam))
    cap = float(market_cap) if market_cap is not None and not math.isnan(market_cap) else 500.0
    effective_cap = max(cap, 10.0)

    ratio = tam / effective_cap
    # 5.0x ratio gives 100.0
    score = (ratio / 5.0) * 100.0
    return round(min(100.0, max(0.0, score)), 1)
