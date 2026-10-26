from dataclasses import dataclass
from typing import List, Optional

from bioseeder.engine.proximity import calculate_proximity_score
from bioseeder.engine.pos_matrix import calculate_pos_score
from bioseeder.engine.dilution import calculate_dilution_score
from bioseeder.engine.asymmetry import calculate_asymmetry_score


@dataclass
class BioAlphaBreakdown:
    composite_score: float
    proximity_score: float
    pos_score: float
    asymmetry_score: float
    dilution_hazard_score: float
    smart_money_score: float
    dilution_flag: bool


def calculate_bio_alpha(
    days_to_event: int,
    therapeutic_area: str,
    phase: str,
    target_tam: Optional[float] = None,
    market_cap: Optional[float] = None,
    cash_runway_months: Optional[float] = None,
    designations: Optional[List[str]] = None,
    insider_score: float = 50.0,
    is_big_pharma: Optional[bool] = None,
    w_prox: float = 0.25,
    w_pos: float = 0.25,
    w_asym: float = 0.20,
    w_fin: float = 0.20,
    w_smart: float = 0.10,
) -> BioAlphaBreakdown:
    """
    Calculate composite Bio-Alpha score (0 to 100) and its sub-components:
    BioAlpha = (w1*Prox + w2*PoS + w3*Asym + w4*Fin + w5*Smart) / (sum of weights)
    """
    effective_market_cap = market_cap if market_cap is not None else 500.0
    effective_tam = target_tam if target_tam is not None else 1000.0

    if is_big_pharma is None:
        is_big_pharma = effective_market_cap >= 2000.0

    s_prox = calculate_proximity_score(days_to_event)
    s_pos = calculate_pos_score(therapeutic_area, phase, designations)
    s_asym = calculate_asymmetry_score(effective_tam, effective_market_cap, is_big_pharma)
    s_fin, dilution_flag = calculate_dilution_score(cash_runway_months)
    effective_insider = 50.0 if insider_score is None else float(insider_score)
    s_smart = min(100.0, max(0.0, effective_insider))

    total_weight = w_prox + w_pos + w_asym + w_fin + w_smart
    if total_weight <= 0:
        total_weight = 1.0

    composite = (
        (w_prox * s_prox)
        + (w_pos * s_pos)
        + (w_asym * s_asym)
        + (w_fin * s_fin)
        + (w_smart * s_smart)
    ) / total_weight

    composite = round(min(100.0, max(0.0, composite)), 1)

    return BioAlphaBreakdown(
        composite_score=composite,
        proximity_score=s_prox,
        pos_score=s_pos,
        asymmetry_score=s_asym,
        dilution_hazard_score=s_fin,
        smart_money_score=s_smart,
        dilution_flag=dilution_flag,
    )
