# tests/test_trade_blueprint.py
"""Trade Blueprint ve son kullanıcı risk/getiri metrikleri doğrulaması."""

from opsi.api import _compute_blueprint_metrics


def test_csp_blueprint_metrics():
    # CSP: Strike 18.5, mid 0.515
    bp = _compute_blueprint_metrics("csp", 18.5, 0.50, 0.53, None)
    assert bp["max_profit"] == 51.5
    assert bp["max_loss"] == round((18.5 - 0.515) * 100, 2)
    assert bp["breakeven"] == round(18.5 - 0.515, 2)


def test_covered_call_blueprint_metrics():
    # Covered Call: Strike 22.0, Spot 20.0, Prem 0.45
    legs_json = '[{"strike": 22.0, "mid": 0.45, "spot": 20.0}]'
    bp = _compute_blueprint_metrics("covered_call", 22.0, 0.40, 0.50, legs_json)
    # max_profit = (22 - 20 + 0.45) * 100 = 245.0
    assert bp["max_profit"] == 245.0
    # max_loss = (20 - 0.45) * 100 = 1955.0
    assert bp["max_loss"] == 1955.0
    # breakeven = 20 - 0.45 = 19.55
    assert bp["breakeven"] == 19.55


def test_bull_put_spread_blueprint_metrics():
    # Bull Put Spread: Sell 18.0P @ 0.45, Buy 16.0P @ 0.15 -> Credit 0.30, Width 2.0
    legs_json = '[{"strike": 18.0, "mid": 0.45}, {"strike": 16.0, "mid": 0.15}]'
    bp = _compute_blueprint_metrics("bull_put_spread", 18.0, 0.40, 0.50, legs_json)
    assert bp["max_profit"] == 30.0
    assert bp["max_loss"] == 170.0
    assert bp["breakeven"] == 17.70
