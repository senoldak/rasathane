import json
from pathlib import Path

def test_seed_files_exist_and_valid():
    seed_dir = Path("capitolseeder/data/seed")
    assert (seed_dir / "politicians.json").exists()
    assert (seed_dir / "committees.json").exists()
    assert (seed_dir / "trades.json").exists()
    
    with open(seed_dir / "politicians.json", "r", encoding="utf-8") as f:
        pols = json.load(f)
        assert len(pols) >= 5
        assert any(p["bioguide_id"] == "P000197" for p in pols)
        
    with open(seed_dir / "committees.json", "r", encoding="utf-8") as f:
        comms = json.load(f)
        assert len(comms) >= 5
        
    with open(seed_dir / "trades.json", "r", encoding="utf-8") as f:
        trades = json.load(f)
        assert len(trades) >= 10
        for t in trades:
            assert t["amount_min"] <= t["amount_max"]
            assert t["amount_midpoint"] == (t["amount_min"] + t["amount_max"]) / 2
            assert "owner_type" in t
            assert "ticker" in t
