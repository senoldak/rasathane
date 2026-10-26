import pytest
from bioseeder.engine.proximity import calculate_proximity_score
from bioseeder.engine.pos_matrix import calculate_pos_score
from bioseeder.engine.dilution import calculate_dilution_score
from bioseeder.engine.asymmetry import calculate_asymmetry_score
from bioseeder.engine.bio_alpha import calculate_bio_alpha, BioAlphaBreakdown


def test_proximity_decay_curve():
    s_t0 = calculate_proximity_score(days_to_event=0)
    s_t1 = calculate_proximity_score(days_to_event=1)
    s_t7 = calculate_proximity_score(days_to_event=7)
    s_t14 = calculate_proximity_score(days_to_event=14)
    s_t30 = calculate_proximity_score(days_to_event=30)
    s_t90 = calculate_proximity_score(days_to_event=90)

    assert s_t0 == 100.0
    assert s_t1 == 100.0
    assert s_t1 > s_t7 > s_t14 > s_t30 > s_t90
    assert round(s_t7, 1) == 81.9
    assert round(s_t30, 1) == 38.0
    assert s_t90 < 10.0


def test_pos_matrix():
    oncology_p1 = calculate_pos_score("Oncology", "Phase 1")
    oncology_p2 = calculate_pos_score("Oncology", "Phase 2")
    oncology_p3 = calculate_pos_score("Oncology", "Phase 3")
    oncology_pdufa = calculate_pos_score("Oncology", "PDUFA")

    assert oncology_p1 == 5.0
    assert oncology_p2 == 18.0
    assert oncology_p3 == 45.0
    assert oncology_pdufa == 88.0

    # Test designations boost
    boosted = calculate_pos_score(
        "Oncology",
        "Phase 3",
        designations=["Breakthrough Therapy", "Priority Review"]
    )
    # 45.0 + 10.0 + 5.0 = 60.0
    assert boosted == 60.0


def test_dilution_hazard():
    # Critical runway (< 6 months)
    score_crit, flag_crit = calculate_dilution_score(cash_runway_months=3.0)
    assert flag_crit is True
    assert score_crit == 12.5  # (3 / 6) * 25

    # Safe runway (>= 24 months)
    score_safe, flag_safe = calculate_dilution_score(cash_runway_months=30.0)
    assert flag_safe is False
    assert score_safe >= 90.0

    # None and NaN handling
    score_none, flag_none = calculate_dilution_score(cash_runway_months=None)
    assert score_none == 50.0
    assert flag_none is False

    score_nan, flag_nan = calculate_dilution_score(cash_runway_months=float("nan"))
    assert score_nan == 50.0
    assert flag_nan is False

    # Negative cash runway clamped to 0.0
    score_neg, flag_neg = calculate_dilution_score(cash_runway_months=-5.0)
    assert score_neg == 0.0
    assert flag_neg is True


def test_proximity_past_events():
    assert calculate_proximity_score(days_to_event=-1) == 0.0
    assert calculate_proximity_score(days_to_event=-30) == 0.0
    assert calculate_proximity_score(days_to_event=-365) == 0.0
    # Day 0 and 1 are 100.0
    assert calculate_proximity_score(days_to_event=0) == 100.0
    assert calculate_proximity_score(days_to_event=1) == 100.0


def test_pos_matrix_new_benchmarks_and_matching():
    # Preclinical benchmark (2.0%)
    onc_pre = calculate_pos_score("Oncology", "Preclinical")
    assert onc_pre == 2.0
    neuro_pre = calculate_pos_score("Neurology", "Preclinical")
    assert neuro_pre == 2.0

    # Approved benchmark (95.0% general, 98.0% rare disease)
    onc_app = calculate_pos_score("Oncology", "Approved")
    assert onc_app == 95.0
    rare_app = calculate_pos_score("Rare Disease", "Approved")
    assert rare_app == 98.0

    # Compound phase string parsing: Phase 1/2 evaluates conservatively at entry phase
    p12 = calculate_pos_score("Oncology", "Phase 1/2")
    assert p12 == 5.0

    # Default fallback for unknown therapeutic area uses DEFAULT_POS
    unknown_ta = calculate_pos_score("Unknown Area", "Phase 3")
    assert unknown_ta == 52.0
    completely_unknown = calculate_pos_score("Unknown Area", "Unknown Phase")
    assert completely_unknown == 50.0


def test_asymmetry_score():
    # Small cap: $500M market cap, $2500M TAM -> 5.0x ratio -> 100.0
    asym_small = calculate_asymmetry_score(target_tam=2500.0, market_cap=500.0, is_big_pharma=False)
    assert asym_small == 100.0

    # Big pharma: $100,000M rev, $2000M peak sales
    asym_big = calculate_asymmetry_score(target_tam=2000.0, market_cap=100000.0, is_big_pharma=True)
    assert 0.0 <= asym_big <= 100.0

    # Continuity check at $2,000M boundary: ensure no 10x cliff drop
    s_just_below = calculate_asymmetry_score(target_tam=1000.0, market_cap=1999.99)
    s_just_above = calculate_asymmetry_score(target_tam=1000.0, market_cap=2000.01)
    assert abs(s_just_below - s_just_above) < 0.1

    # NaN and None handling
    assert calculate_asymmetry_score(target_tam=None, market_cap=500.0) == 0.0
    assert calculate_asymmetry_score(target_tam=float("nan"), market_cap=500.0) == 0.0
    assert calculate_asymmetry_score(target_tam=1000.0, market_cap=None) == 40.0
    assert calculate_asymmetry_score(target_tam=1000.0, market_cap=0.0) == 100.0


def test_composite_bio_alpha_calculation():
    breakdown = calculate_bio_alpha(
        days_to_event=7,
        therapeutic_area="Rare Disease",
        phase="Phase 3",
        designations=["Fast Track", "Orphan Drug"],
        target_tam=1500.0,
        market_cap=300.0,
        cash_runway_months=18.0,
        insider_score=75.0,
    )

    assert isinstance(breakdown, BioAlphaBreakdown)
    assert 0.0 <= breakdown.composite_score <= 100.0
    assert breakdown.proximity_score > 80.0
    assert breakdown.dilution_flag is False

    # Optional fields missing (None) should gracefully fallback
    fallback_breakdown = calculate_bio_alpha(
        days_to_event=14,
        therapeutic_area="Oncology",
        phase="Phase 2",
        designations=None,
        target_tam=None,
        market_cap=None,
        cash_runway_months=None,
        insider_score=None,
    )
    assert 0.0 <= fallback_breakdown.composite_score <= 100.0
    assert fallback_breakdown.dilution_flag is False

