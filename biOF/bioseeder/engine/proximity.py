import math


def calculate_proximity_score(days_to_event: int, tau: float = 30.0) -> float:
    """
    Calculate catalyst proximity and velocity score using exponential decay:
    - If days_to_event < 0 (event in the past): returns 0.0
    - If days_to_event == 0 or 1: returns 100.0
    - If days_to_event > 1: S_prox = 100 * exp(-(days - 1) / tau)
    """
    if days_to_event < 0:
        return 0.0

    delta_t = max(0, days_to_event - 1)
    score = 100.0 * math.exp(-delta_t / tau)
    return round(min(100.0, max(0.0, score)), 1)
