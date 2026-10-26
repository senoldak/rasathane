import re
from typing import Dict, Any

def _match_role(title: str, is_officer: bool, is_director: bool, is_ten_percent: bool) -> tuple[str, int]:
    """Determine role category and points based on title and relationship flags."""
    title_upper = (title or "").upper()

    is_subordinate = any(sub in title_upper for sub in ("DEPUTY", "ASSISTANT", "VICE PRESIDENT", "VP"))

    if ("CHIEF EXECUTIVE OFFICER" in title_upper or re.search(r"\bCEO\b", title_upper)) and not any(sub in title_upper for sub in ("DEPUTY", "ASSISTANT")):
        return ("CEO", 30)
    elif ("CHIEF FINANCIAL OFFICER" in title_upper or re.search(r"\bCFO\b", title_upper)) and not any(sub in title_upper for sub in ("DEPUTY", "ASSISTANT")):
        return ("CFO", 25)
    elif ("CHIEF OPERATING OFFICER" in title_upper or re.search(r"\bCOO\b", title_upper) or re.search(r"\bPRESIDENT\b", title_upper)) and not is_subordinate:
        return ("COO/President", 20)
    elif is_director or "DIRECTOR" in title_upper:
        return ("Director", 15)
    elif is_ten_percent or "10%" in title_upper or re.search(r"\b10%\s*OWNER\b", title_upper) or "BENEFICIAL OWNER" in title_upper:
        return ("10% Owner", 10)
    elif is_officer or is_subordinate or "OFFICER" in title_upper:
        return ("Officer", 15)
    return ("Other", 5)

def compute_conviction_score(trade: Dict[str, Any], cluster_count: int = 1) -> Dict[str, Any]:
    """
    Computes a quantitative Conviction Score (0-100) for an insider trade.
    Returns:
        {
            "score": int,
            "breakdown": {
                "role": str,
                "role_points": int,
                "value_points": int,
                "increase_points": int,
                "cluster_points": int,
                "discretionary_points": int,
                "raw_total": int
            }
        }
    """
    trans_code = trade.get("transaction_code", "P").upper()
    title = trade.get("insider_title", "")
    is_officer = bool(trade.get("is_officer", False))
    is_director = bool(trade.get("is_director", False))
    is_ten_percent = bool(trade.get("is_ten_percent", False))
    value = float(trade.get("value", 0.0) or 0.0)
    shares = float(trade.get("shares", 0.0) or 0.0)
    shares_owned_after = float(trade.get("shares_owned_after", 0.0) or 0.0)
    is_10b5_1 = bool(trade.get("is_10b5_1", False))

    role_name, role_pts = _match_role(title, is_officer, is_director, is_ten_percent)

    # 1. Transaction Type Check
    # If not an open-market purchase ('P'), we cap or reduce conviction significantly
    if trans_code != "P":
        # For sales, score indicates anomalous signal strength (0-30 max)
        sale_pts = 10 if not is_10b5_1 else 0
        if value >= 1000000.0:
            sale_pts += 15
        return {
            "score": min(sale_pts, 30),
            "breakdown": {
                "role": role_name,
                "role_points": 0,
                "value_points": sale_pts,
                "increase_points": 0,
                "cluster_points": 0,
                "discretionary_points": 0,
                "raw_total": sale_pts
            }
        }

    # 2. Dollar Value points
    value_pts = 0
    if value >= 1000000.0:
        value_pts = 35
    elif value >= 500000.0:
        value_pts = 25
    elif value >= 100000.0:
        value_pts = 15
    elif value >= 25000.0:
        value_pts = 5

    # 3. Holding Increase % points
    increase_pts = 0
    prior_shares = shares_owned_after - shares
    if shares_owned_after == shares and shares > 0:
        # Initiating a new position (prior shares were strictly 0)
        increase_pts = 25
    elif shares_owned_after > shares and prior_shares > 0:
        pct_increase = (shares / prior_shares) * 100.0
        if pct_increase >= 50.0:
            increase_pts = 25
        elif pct_increase >= 20.0:
            increase_pts = 15
    else:
        # shares_owned_after < shares or omitted; incomplete or contradictory data
        increase_pts = 0

    # 4. Cluster Buying points
    cluster_pts = 30 if cluster_count >= 2 else 0

    # 5. Discretionary points (Not a scheduled 10b5-1 plan)
    discretionary_pts = 10 if not is_10b5_1 else 0

    raw_total = role_pts + value_pts + increase_pts + cluster_pts + discretionary_pts
    final_score = min(raw_total, 100)

    return {
        "score": final_score,
        "breakdown": {
            "role": role_name,
            "role_points": role_pts,
            "value_points": value_pts,
            "increase_points": increase_pts,
            "cluster_points": cluster_pts,
            "discretionary_points": discretionary_pts,
            "raw_total": raw_total
        }
    }
