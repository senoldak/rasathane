from typing import Tuple, List, Dict, Any, Optional
from capitolseeder.config import get_settings
from capitolseeder.db.models import StockTrade, Politician, CapitolAlphaScore

settings = get_settings()

def compute_size_score(midpoint: float) -> float:
    """
    Logarithmically scaled statutory size score:
    <= $15K -> 20
    $15K - $100K -> 50
    $100K - $500K -> 75
    $500K - $1M -> 85
    > $1M -> 100
    """
    if midpoint <= 15000.0:
        return 20.0
    elif midpoint <= 100000.0:
        return 50.0
    elif midpoint <= 500000.0:
        return 75.0
    elif midpoint <= 1000000.0:
        return 85.0
    else:
        return 100.0

def compute_asset_score(asset_type: str) -> float:
    """
    Asset conviction score:
    Call Option -> 100 (leveraged bullish bet)
    Stock -> 70 (common equity purchase)
    Put Option -> 50 (bearish hedge/speculation)
    Bond -> 10 (routine yield)
    """
    norm = asset_type.lower()
    if "put" in norm:
        return 50.0
    elif "call" in norm or "option" in norm:
        return 100.0
    elif "stock" in norm or "equity" in norm:
        return 70.0
    elif "bond" in norm or "treasury" in norm:
        return 10.0
    return 40.0

def compute_decay_penalty(lag_days: int) -> float:
    """
    Filing freshness penalty:
    <= 5 days -> 0
    5 < lag <= 20 days -> 5
    20 < lag <= 45 days -> 15
    > 45 days (STOCK Act Violation) -> 30
    """
    if lag_days <= 5:
        return 0.0
    elif lag_days <= 20:
        return 5.0
    elif lag_days <= 45:
        return 15.0
    else:
        return 30.0

# Known sector / company keyword associations
TICKER_KEYWORD_MAP = {
    "LMT": ["defense", "aerospace", "weapons", "procurement", "munitions", "missiles"],
    "RTX": ["defense", "aerospace", "weapons", "radars", "missiles"],
    "NOC": ["defense", "aerospace", "stealth", "bombers", "procurement"],
    "PLTR": ["defense", "intelligence", "cybersecurity", "software", "artificial intelligence"],
    "MSFT": ["technology", "cloud", "software", "cybersecurity", "artificial intelligence"],
    "NVDA": ["semiconductors", "technology", "artificial intelligence", "chips", "hardware"],
    "AVGO": ["semiconductors", "chips", "technology", "networking"],
    "BA": ["aerospace", "defense", "aviation", "procurement", "nasa"],
    "CVX": ["oil", "gas", "energy", "lng", "pipelines", "petroleum"]
}

def compute_committee_conflict_score(
    ticker: str,
    sector: str,
    jurisdiction_keywords: List[str],
    is_chair_or_ranking: bool = False
) -> Tuple[float, str]:
    """
    Computes committee conflict score (0 - 100) and rationale.
    """
    ticker_clean = ticker.upper()
    company_keywords = set(TICKER_KEYWORD_MAP.get(ticker_clean, []))
    if sector:
        for word in sector.lower().replace("/", " ").split():
            company_keywords.add(word)

    jurisdiction_set = {k.lower() for k in jurisdiction_keywords}
    overlap = company_keywords.intersection(jurisdiction_set)
    
    if overlap:
        base_score = 90.0 if len(overlap) >= 2 else 75.0
        rationale = f"Direct jurisdiction overlap on keywords: {', '.join(sorted(overlap))}."
    else:
        base_score = 0.0
        rationale = "No direct committee jurisdiction match identified."

    if is_chair_or_ranking and overlap:
        base_score += 25.0
        rationale += " +25 Leadership bonus applied (Committee Chair / Ranking Member)."

    score = min(100.0, max(0.0, base_score))
    return score, rationale

def compute_composite_score(
    conflict_score: float,
    cluster_score: float,
    winrate_score: float,
    size_score: float,
    asset_score: float,
    lag_days: int,
    w1: Optional[float] = None,
    w2: Optional[float] = None,
    w3: Optional[float] = None,
    w4: Optional[float] = None,
    w5: Optional[float] = None
) -> float:
    """
    Composite Score = clamp(w1*C + w2*B + w3*P + w4*S + w5*A - Lambda_decay, 0, 100)
    """
    w1 = w1 if w1 is not None else settings.weight_conflict
    w2 = w2 if w2 is not None else settings.weight_cluster
    w3 = w3 if w3 is not None else settings.weight_winrate
    w4 = w4 if w4 is not None else settings.weight_size
    w5 = w5 if w5 is not None else settings.weight_asset

    penalty = compute_decay_penalty(lag_days)
    raw = (
        w1 * conflict_score +
        w2 * cluster_score +
        w3 * winrate_score +
        w4 * size_score +
        w5 * asset_score -
        penalty
    )
    return round(min(100.0, max(0.0, raw)), 2)

def compute_winrate_score(win_rate: Optional[float], has_history: bool = True) -> float:
    """
    Computes win rate component score (0.0 to 100.0).
    If a politician has historical trades and a 0.0% win rate, returns 0.0.
    If a politician has no trade history, default neutral prior is 50.0.
    """
    if win_rate is not None and win_rate > 0:
        return float(win_rate)
    elif has_history:
        return 0.0
    return 50.0

def score_trade(
    trade: StockTrade,
    politician: Politician,
    cluster_score: float = 0.0
) -> CapitolAlphaScore:
    """
    Evaluates a StockTrade and creates a CapitolAlphaScore record.
    """
    # Evaluate conflict on a per-committee basis to isolate leadership bonus
    best_conflict_score = 0.0
    best_conflict_rationale = "No direct committee jurisdiction match identified."

    for cm in getattr(politician, "committees", []):
        cm_keywords = cm.jurisdiction_keywords if isinstance(cm.jurisdiction_keywords, list) else []
        is_cm_leader = cm.role in {"Chair", "Ranking Member"}
        cm_score, cm_rationale = compute_committee_conflict_score(
            ticker=trade.ticker,
            sector="",
            jurisdiction_keywords=cm_keywords,
            is_chair_or_ranking=is_cm_leader
        )
        if cm_score > best_conflict_score:
            best_conflict_score = cm_score
            best_conflict_rationale = f"[{cm.committee_name} ({cm.role})] {cm_rationale}"

    conflict_score = best_conflict_score
    conflict_rationale = best_conflict_rationale

    from sqlalchemy import inspect
    pol_insp = inspect(politician)
    has_trades_loaded = "trades" in pol_insp.dict and bool(pol_insp.dict["trades"])
    has_history = bool((politician.total_volume and politician.total_volume > 0) or has_trades_loaded)
    winrate_score = compute_winrate_score(politician.win_rate, has_history=has_history)

    size_score = compute_size_score(trade.amount_midpoint)
    asset_score = compute_asset_score(trade.asset_type)
    decay_penalty = compute_decay_penalty(trade.filing_lag_days)

    composite = compute_composite_score(
        conflict_score=conflict_score,
        cluster_score=cluster_score,
        winrate_score=winrate_score,
        size_score=size_score,
        asset_score=asset_score,
        lag_days=trade.filing_lag_days,
        w1=settings.weight_conflict,
        w2=settings.weight_cluster,
        w3=settings.weight_winrate,
        w4=settings.weight_size,
        w5=settings.weight_asset
    )

    rationale = {
        "conflict": conflict_rationale,
        "cluster_score": cluster_score,
        "winrate_score": winrate_score,
        "size_score": size_score,
        "asset_score": asset_score,
        "decay_penalty": decay_penalty,
        "composite": composite
    }

    return CapitolAlphaScore(
        trade_id=trade.id,
        conflict_score=conflict_score,
        cluster_score=cluster_score,
        winrate_score=winrate_score,
        size_score=size_score,
        asset_score=asset_score,
        decay_penalty=decay_penalty,
        composite_alpha_score=composite,
        rationale=rationale
    )
