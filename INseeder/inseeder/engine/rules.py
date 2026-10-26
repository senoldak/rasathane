import json
from typing import List, Dict, Any

def evaluate_rules(trade: Dict[str, Any], score: int, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evaluates an insider trade against active rules.
    Returns a list of matching rule dictionaries.
    """
    matched_rules = []
    trade_value = float(trade.get("value", 0.0) or 0.0)
    trans_code = trade.get("transaction_code", "P").upper()
    title_upper = (trade.get("insider_title", "") or "").upper()
    is_director = bool(trade.get("is_director", False))
    is_officer = bool(trade.get("is_officer", False))
    is_ten_percent = bool(trade.get("is_ten_percent", False))

    for rule in rules:
        if not rule.get("is_active", 1):
            continue

        # 1. Score check
        min_score = rule.get("min_score", 0)
        if score < min_score:
            continue

        # 2. Value check
        min_value = float(rule.get("min_value", 0.0) or 0.0)
        if trade_value < min_value:
            continue

        # 3. Transaction type check
        allowed_types_raw = rule.get("allowed_types", '["P"]')
        if isinstance(allowed_types_raw, str):
            try:
                allowed_types = json.loads(allowed_types_raw)
            except json.JSONDecodeError:
                allowed_types = ["P"]
        else:
            allowed_types = allowed_types_raw

        if allowed_types:
            allowed_types_upper = [str(t).upper() for t in allowed_types]
            if trans_code not in allowed_types_upper:
                continue

        # 4. Role check
        allowed_roles_raw = rule.get("allowed_roles", '["CEO","CFO","Director"]')
        if isinstance(allowed_roles_raw, str):
            try:
                allowed_roles = json.loads(allowed_roles_raw)
            except json.JSONDecodeError:
                allowed_roles = ["CEO", "CFO", "Director"]
        else:
            allowed_roles = allowed_roles_raw

        role_matched = False
        if not allowed_roles:
            role_matched = True
        else:
            for r in allowed_roles:
                r_upper = str(r).upper()
                if r_upper == "CEO" and ("CEO" in title_upper or "CHIEF EXECUTIVE" in title_upper):
                    role_matched = True
                    break
                elif r_upper == "CFO" and ("CFO" in title_upper or "CHIEF FINANCIAL" in title_upper):
                    role_matched = True
                    break
                elif r_upper == "COO" and ("COO" in title_upper or "CHIEF OPERATING" in title_upper):
                    role_matched = True
                    break
                elif r_upper == "PRESIDENT" and ("PRESIDENT" in title_upper):
                    role_matched = True
                    break
                elif r_upper in ("DIRECTOR", "DIR") and (is_director or "DIRECTOR" in title_upper):
                    role_matched = True
                    break
                elif r_upper in ("10%", "10% OWNER", "TEN PERCENT OWNER", "TEN PERCENT") and (is_ten_percent or "10%" in title_upper):
                    role_matched = True
                    break
                elif r_upper in ("OFFICER", "VP", "VICE PRESIDENT") and (is_officer or "OFFICER" in title_upper or "VP" in title_upper or "VICE PRESIDENT" in title_upper):
                    role_matched = True
                    break

        if not role_matched:
            continue

        matched_rules.append(rule)

    return matched_rules
