import pytest
import datetime
from pathlib import Path
from capitolseeder.ingestion.ocr_engine import (
    parse_amount_bracket,
    calculate_stock_act_lag,
    preprocess_image_for_ocr,
    extract_pdf_trades_native,
    extract_image_trades_ocr
)

def test_amount_bracket_parsing():
    # Regular bracket
    min_val, max_val, mid_val = parse_amount_bracket("$15,001 - $50,000")
    assert min_val == 15001.0
    assert max_val == 50000.0
    assert mid_val == 32500.5
    
    # Open-ended $50M+
    min_val, max_val, mid_val = parse_amount_bracket("$50,000,000+")
    assert min_val == 50000000.0
    assert max_val == 100000000.0
    assert mid_val == 75000000.0

    # Complex string with words containing 't' and 'o' that previously broke on [ -to]+
    min_val, max_val, mid_val = parse_amount_bracket("$15,001 - $50,000 (Joint Ownership - Auto)")
    assert min_val == 15001.0
    assert max_val == 50000.0
    assert mid_val == 32500.5

def test_stock_act_lag_calculation():
    tx_date = datetime.date(2024, 1, 1)
    # Timely (20 days)
    disc_date = datetime.date(2024, 1, 21)
    lag, is_viol, sev = calculate_stock_act_lag(tx_date, disc_date)
    assert lag == 20
    assert not is_viol
    assert sev == "None"
    
    # Moderate violation (55 days)
    disc_date_mod = datetime.date(2024, 2, 25)
    lag, is_viol, sev = calculate_stock_act_lag(tx_date, disc_date_mod)
    assert lag == 55
    assert is_viol
    assert sev == "Moderate"
    
    # Severe violation (95 days)
    disc_date_sev = datetime.date(2024, 4, 5)
    lag, is_viol, sev = calculate_stock_act_lag(tx_date, disc_date_sev)
    assert lag == 95
    assert is_viol
    assert sev == "Severe"

    # Invalid chronological order (disclosure before transaction date)
    disc_date_past = datetime.date(2023, 12, 1)
    lag, is_viol, sev = calculate_stock_act_lag(tx_date, disc_date_past)
    assert lag < 0
    assert not is_viol
    assert sev == "InvalidDate"

def test_extract_fixtures():
    seed_dir = Path("capitolseeder/data/seed")
    pdf_path = seed_dir / "sample_ptr_digital.pdf"
    if pdf_path.exists():
        trades = extract_pdf_trades_native(str(pdf_path))
        assert isinstance(trades, list)
        
    png_path = seed_dir / "sample_ptr_scanned.png"
    if png_path.exists():
        ocr_result = extract_image_trades_ocr(str(png_path))
        assert isinstance(ocr_result, dict)
        assert "raw_text" in ocr_result
