import pytest
from capitolseeder.engine.scoring_engine import (
    compute_composite_score,
    compute_size_score,
    compute_asset_score,
    compute_decay_penalty,
    compute_committee_conflict_score
)

def test_composite_score_calculation():
    # C=95, B=100, P=80, S=75, A=100, Lag=4 (decay=0)
    # 0.35*95 + 0.25*100 + 0.15*80 + 0.15*75 + 0.10*100 - 0 = 33.25 + 25 + 12 + 11.25 + 10 = 91.5
    score = compute_composite_score(
        conflict_score=95.0,
        cluster_score=100.0,
        winrate_score=80.0,
        size_score=75.0,
        asset_score=100.0,
        lag_days=4
    )
    assert round(score, 2) == 91.5
    
    # Test decay penalty on late filing (lag=50 -> penalty=30)
    # 91.5 - 30 = 61.5
    score_late = compute_composite_score(
        conflict_score=95.0,
        cluster_score=100.0,
        winrate_score=80.0,
        size_score=75.0,
        asset_score=100.0,
        lag_days=50
    )
    assert round(score_late, 2) == 61.5

def test_piecewise_size_and_asset_scores():
    assert compute_size_score(10000.0) == 20.0
    assert compute_size_score(50000.0) == 50.0
    assert compute_size_score(250000.0) == 75.0
    assert compute_size_score(750000.0) == 85.0
    assert compute_size_score(2000000.0) == 100.0

    assert compute_asset_score("Call_Option") == 100.0
    assert compute_asset_score("Stock") == 70.0
    assert compute_asset_score("Put_Option") == 50.0
    assert compute_asset_score("Bond") == 10.0

    assert compute_decay_penalty(3) == 0.0
    assert compute_decay_penalty(12) == 5.0
    assert compute_decay_penalty(30) == 15.0
    assert compute_decay_penalty(50) == 30.0

def test_committee_conflict_scoring():
    # Armed services committee member buying LMT (defense contractor)
    keywords = ["defense", "aerospace", "weapons", "procurement"]
    score, rationale = compute_committee_conflict_score("LMT", "Industrials / Defense", keywords, is_chair_or_ranking=True)
    assert score >= 95.0
    assert "Chair" in rationale or "Ranking" in rationale or "Leadership" in rationale

def test_committee_leadership_bonus_isolation():
    # Case 1: Chair of unrelated committee (e.g. Agriculture) trading LMT
    score_unrelated, _ = compute_committee_conflict_score(
        "LMT", "Industrials / Defense", ["agriculture", "farming", "nutrition"], is_chair_or_ranking=True
    )
    assert score_unrelated == 0.0

    # Case 2: Chair of matching committee trading LMT
    score_related, rationale = compute_committee_conflict_score(
        "LMT", "Industrials / Defense", ["defense", "aerospace", "weapons"], is_chair_or_ranking=True
    )
    assert score_related == 100.0
    assert "Leadership" in rationale

def test_zero_winrate_scoring():
    from capitolseeder.engine.scoring_engine import compute_winrate_score
    assert compute_winrate_score(0.0) == 0.0
    assert compute_winrate_score(50.0) == 50.0
    assert compute_winrate_score(100.0) == 100.0
