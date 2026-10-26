import pytest
import datetime
from capitolseeder.ingestion.market_data import calculate_trade_alpha, get_ticker_quote

def test_calculate_trade_alpha():
    res = calculate_trade_alpha(
        ticker="NVDA",
        trade_date=datetime.date(2024, 6, 26),
        disc_date=datetime.date(2024, 7, 2),
        price_tx=126.09,
        price_disc=122.58,
        ret_90d=32.6,
        spy_ret_90d=5.8
    )
    assert res["alpha_90d"] == round(32.6 - 5.8, 2)
    assert res["price_at_transaction"] == 126.09
    assert res["price_at_disclosure"] == 122.58

def test_get_ticker_quote():
    # Verify ticker quote structure (falls back to mock/seed if offline)
    quote = get_ticker_quote("NVDA")
    assert quote["ticker"] == "NVDA"
    assert quote["price"] > 0
