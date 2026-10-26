import math
from typing import Optional, Tuple


def calculate_dilution_score(cash_runway_months: Optional[float]) -> Tuple[float, bool]:
    """
    Calculate financial health score and dilution hazard flag.
    - If runway is None or NaN: Neutral score (50.0, False)
    - If runway < 6 months: High dilution hazard, score <= 25.
    - If 6 <= runway < 12 months: Moderate dilution hazard (25-60).
    - If 12 <= runway < 24 months: Low dilution hazard (60-90).
    - If runway >= 24 months: Negligible dilution risk (90-100).

    Returns:
        (financial_score, dilution_flag)
    """
    if cash_runway_months is None or math.isnan(cash_runway_months):
        return (50.0, False)

    runway = float(cash_runway_months)

    if runway < 6.0:
        score = max(0.0, (runway / 6.0) * 25.0) if runway > 0 else 0.0
        return (round(score, 1), True)

    if runway < 12.0:
        score = 25.0 + ((runway - 6.0) / 6.0) * 35.0
        return (round(score, 1), False)

    if runway < 24.0:
        score = 60.0 + ((runway - 12.0) / 12.0) * 30.0
        return (round(score, 1), False)

    # 24+ months
    score = min(100.0, 90.0 + ((runway - 24.0) / 12.0) * 10.0)
    return (round(score, 1), False)
