import pytest
import datetime
from capitolseeder.engine.cluster_detector import detect_clusters_from_trades

def test_detect_clusters_from_trades():
    trades = [
        # Pelosi (Democrat) buys MSFT on 2024-07-02
        {"id": 1, "ticker": "MSFT", "bioguide_id": "P000197", "party": "Democrat", "transaction_date": datetime.date(2024, 7, 2)},
        # McCaul (Republican) buys MSFT on 2024-07-05 (3 days later)
        {"id": 2, "ticker": "MSFT", "bioguide_id": "M001157", "party": "Republican", "transaction_date": datetime.date(2024, 7, 5)},
        # Single trade for NVDA
        {"id": 3, "ticker": "NVDA", "bioguide_id": "P000197", "party": "Democrat", "transaction_date": datetime.date(2024, 6, 26)}
    ]
    clusters = detect_clusters_from_trades(trades, window_days=14)
    assert len(clusters) == 1
    c = clusters[0]
    assert c["ticker"] == "MSFT"
    assert c["cluster_score"] == 100.0  # Bipartisan cluster
    assert c["democrat_count"] == 1
    assert c["republican_count"] == 1

def test_cluster_detector_purchase_only_and_multi_window():
    # 1. Rejection of mixed Buy + Sell
    trades_buy_sell = [
        {"id": 1, "ticker": "AAPL", "bioguide_id": "P000197", "party": "Democrat", "transaction_type": "Purchase", "transaction_date": datetime.date(2024, 7, 2)},
        {"id": 2, "ticker": "AAPL", "bioguide_id": "M001157", "party": "Republican", "transaction_type": "Sale (Full)", "transaction_date": datetime.date(2024, 7, 5)},
    ]
    clusters = detect_clusters_from_trades(trades_buy_sell, window_days=14)
    assert len(clusters) == 0

    # 2. Multi-window preservation: Two distinct bipartisan clusters in 2023 and 2024 for MSFT
    trades_multi_year = [
        # 2023 cluster
        {"id": 10, "ticker": "MSFT", "bioguide_id": "P000197", "party": "Democrat", "transaction_type": "Purchase", "transaction_date": datetime.date(2023, 1, 10)},
        {"id": 11, "ticker": "MSFT", "bioguide_id": "M001157", "party": "Republican", "transaction_type": "Purchase", "transaction_date": datetime.date(2023, 1, 15)},
        # 2024 cluster
        {"id": 12, "ticker": "MSFT", "bioguide_id": "P000197", "party": "Democrat", "transaction_type": "Purchase", "transaction_date": datetime.date(2024, 6, 10)},
        {"id": 13, "ticker": "MSFT", "bioguide_id": "M001157", "party": "Republican", "transaction_type": "Purchase", "transaction_date": datetime.date(2024, 6, 15)},
    ]
    clusters_multi = detect_clusters_from_trades(trades_multi_year, window_days=14)
    assert len(clusters_multi) == 2
