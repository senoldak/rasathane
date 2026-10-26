from typing import List, Optional

# Empirical statistical probability of success benchmarks by therapeutic area & phase
POS_MATRIX = {
    "oncology": {
        "preclinical": 2.0,
        "phase 1": 5.0,
        "phase 2": 18.0,
        "phase 3": 45.0,
        "pdufa": 88.0,
        "nda": 88.0,
        "bla": 88.0,
        "nda/bla": 88.0,
        "approved": 95.0,
    },
    "neurology": {
        "preclinical": 2.0,
        "phase 1": 8.0,
        "phase 2": 15.0,
        "phase 3": 48.0,
        "pdufa": 85.0,
        "nda": 85.0,
        "bla": 85.0,
        "nda/bla": 85.0,
        "approved": 95.0,
    },
    "cns": {
        "preclinical": 2.0,
        "phase 1": 8.0,
        "phase 2": 15.0,
        "phase 3": 48.0,
        "pdufa": 85.0,
        "nda": 85.0,
        "bla": 85.0,
        "nda/bla": 85.0,
        "approved": 95.0,
    },
    "rare disease": {
        "preclinical": 3.0,
        "phase 1": 22.0,
        "phase 2": 38.0,
        "phase 3": 68.0,
        "pdufa": 93.0,
        "nda": 93.0,
        "bla": 93.0,
        "nda/bla": 93.0,
        "approved": 98.0,
    },
    "hematology": {
        "preclinical": 3.0,
        "phase 1": 22.0,
        "phase 2": 38.0,
        "phase 3": 68.0,
        "pdufa": 93.0,
        "nda": 93.0,
        "bla": 93.0,
        "nda/bla": 93.0,
        "approved": 98.0,
    },
    "immunology": {
        "preclinical": 2.5,
        "phase 1": 12.0,
        "phase 2": 25.0,
        "phase 3": 55.0,
        "pdufa": 89.0,
        "nda": 89.0,
        "bla": 89.0,
        "nda/bla": 89.0,
        "approved": 96.0,
    },
    "autoimmune": {
        "preclinical": 2.5,
        "phase 1": 12.0,
        "phase 2": 25.0,
        "phase 3": 55.0,
        "pdufa": 89.0,
        "nda": 89.0,
        "bla": 89.0,
        "nda/bla": 89.0,
        "approved": 96.0,
    },
    "infectious": {
        "preclinical": 2.5,
        "phase 1": 14.0,
        "phase 2": 28.0,
        "phase 3": 62.0,
        "pdufa": 90.0,
        "nda": 90.0,
        "bla": 90.0,
        "nda/bla": 90.0,
        "approved": 96.0,
    },
}

DEFAULT_POS = {
    "preclinical": 2.0,
    "phase 1": 10.0,
    "phase 2": 22.0,
    "phase 3": 52.0,
    "pdufa": 88.0,
    "nda": 88.0,
    "bla": 88.0,
    "nda/bla": 88.0,
    "approved": 95.0,
}

DESIGNATION_BOOSTS = {
    "breakthrough therapy": 10.0,
    "priority review": 5.0,
    "orphan drug": 4.0,
    "fast track": 3.0,
}


def calculate_pos_score(
    therapeutic_area: str,
    phase: str,
    designations: Optional[List[str]] = None,
) -> float:
    """
    Calculate baseline statistical Probability of Success (PoS) based on
    therapeutic area, clinical phase, and special regulatory designations.
    """
    area_key = therapeutic_area.lower().strip()
    phase_key = phase.lower().strip()

    # Find matching therapeutic area (longest key first)
    area_dict = DEFAULT_POS
    sorted_area_keys = sorted(POS_MATRIX.keys(), key=len, reverse=True)
    for k in sorted_area_keys:
        if k in area_key:
            area_dict = POS_MATRIX[k]
            break

    # Find matching phase (longest key first)
    base_pos = 50.0
    sorted_phase_keys = sorted(area_dict.keys(), key=len, reverse=True)
    for pk in sorted_phase_keys:
        if pk in phase_key:
            base_pos = area_dict[pk]
            break

    # Add regulatory designation boosts
    boost = 0.0
    if designations:
        for des in designations:
            des_key = des.lower().strip()
            for dk, dval in DESIGNATION_BOOSTS.items():
                if dk in des_key:
                    boost += dval

    total_score = min(100.0, max(0.0, base_pos + boost))
    return round(total_score, 1)
