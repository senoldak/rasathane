import datetime
from typing import List, Dict, Any
from collections import defaultdict

def _extract_trade_field(t: Any, key: str, default: Any = None) -> Any:
    if isinstance(t, dict):
        return t.get(key, default)
    if hasattr(t, key):
        val = getattr(t, key)
        return val if val is not None else default
    if key == "party" and hasattr(t, "politician") and t.politician:
        return t.politician.party
    return default

def detect_clusters_from_trades(trades: List[Any], window_days: int = 14) -> List[Dict[str, Any]]:
    """
    Detects bipartisan and intra-party cluster trades within a rolling window_days.
    Supports both dictionaries and StockTrade ORM model instances.
    B = 100 if both Democrats and Republicans purchased the same ticker.
    B = 60 if 3+ members of the same party purchased the ticker.
    B = 30 if 2 members of the same party purchased the ticker.
    """
    # Group trades by ticker (only Purchases form consensus buying clusters)
    ticker_trades = defaultdict(list)
    for t in trades:
        tx_type = _extract_trade_field(t, "transaction_type", "Purchase")
        if tx_type != "Purchase":
            continue
        ticker = (_extract_trade_field(t, "ticker", "") or "").upper()
        if ticker:
            ticker_trades[ticker].append(t)

    clusters = []

    for ticker, t_list in ticker_trades.items():
        if len(t_list) < 2:
            continue
            
        # Sort by transaction date
        sorted_trades = sorted(t_list, key=lambda x: _extract_trade_field(x, "transaction_date"))
        
        # Scan rolling windows
        n = len(sorted_trades)
        for i in range(n):
            window_group = [sorted_trades[i]]
            base_date = _extract_trade_field(sorted_trades[i], "transaction_date")
            
            for j in range(i + 1, n):
                t_date = _extract_trade_field(sorted_trades[j], "transaction_date")
                diff = (t_date - base_date).days
                if diff <= window_days:
                    window_group.append(sorted_trades[j])
                else:
                    break

            if len(window_group) >= 2:
                # Count parties and unique politicians
                parties = set()
                politicians = set()
                dem_count = 0
                rep_count = 0
                
                for trade in window_group:
                    party = _extract_trade_field(trade, "party")
                    pol_id = _extract_trade_field(trade, "bioguide_id")
                    if pol_id not in politicians:
                        politicians.add(pol_id)
                        parties.add(party)
                        if party == "Democrat":
                            dem_count += 1
                        elif party == "Republican":
                            rep_count += 1


                if len(politicians) >= 2:
                    if dem_count >= 1 and rep_count >= 1:
                        cluster_score = 100.0
                        signal_type = "Bipartisan Cluster"
                    elif len(politicians) >= 3:
                        cluster_score = 60.0
                        signal_type = "Party Consensus Cluster (3+)"
                    else:
                        cluster_score = 30.0
                        signal_type = "Dual Member Cluster"

                    clusters.append({
                        "ticker": ticker,
                        "cluster_score": cluster_score,
                        "signal_type": signal_type,
                        "start_date": _extract_trade_field(window_group[0], "transaction_date"),
                        "end_date": _extract_trade_field(window_group[-1], "transaction_date"),
                        "democrat_count": dem_count,
                        "republican_count": rep_count,
                        "total_members": len(politicians),
                        "trades": [
                            {
                                "id": _extract_trade_field(tr, "id"),
                                "ticker": _extract_trade_field(tr, "ticker"),
                                "bioguide_id": _extract_trade_field(tr, "bioguide_id"),
                                "party": _extract_trade_field(tr, "party"),
                                "politician_name": _extract_trade_field(tr, "politician_name", f"{getattr(getattr(tr, 'politician', None), 'first_name', '')} {getattr(getattr(tr, 'politician', None), 'last_name', '')}".strip()),
                                "transaction_date": _extract_trade_field(tr, "transaction_date"),
                                "amount_range_str": _extract_trade_field(tr, "amount_range_str"),
                                "owner_type": _extract_trade_field(tr, "owner_type")
                            }
                            for tr in window_group
                        ]
                    })


    # Deduplicate overlapping clusters per ticker while preserving temporal history
    final_clusters = []
    by_ticker = defaultdict(list)
    for c in clusters:
        by_ticker[c["ticker"]].append(c)

    for ticker, c_list in by_ticker.items():
        sorted_c = sorted(c_list, key=lambda x: (x["start_date"], -x["cluster_score"]))
        merged = []
        for c in sorted_c:
            if not merged:
                merged.append(c)
                continue
            last = merged[-1]
            if (c["start_date"] - last["start_date"]).days <= window_days:
                if c["cluster_score"] > last["cluster_score"]:
                    merged[-1] = c
            else:
                merged.append(c)
        final_clusters.extend(merged)

    return sorted(final_clusters, key=lambda x: (x["start_date"], -x["cluster_score"]), reverse=True)
