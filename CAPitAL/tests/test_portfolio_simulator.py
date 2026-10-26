import pytest
import datetime
from capitolseeder.engine.portfolio_simulator import calculate_portfolio_metrics, simulate_trades_portfolio

def test_portfolio_metrics_calculation():
    returns_series = [0.02, 0.05, -0.01, 0.04, 0.03]
    spy_returns_series = [0.01, 0.02, 0.00, 0.01, 0.01]
    metrics = calculate_portfolio_metrics(returns_series, spy_returns_series)
    assert metrics["cumulative_return"] > 0
    assert metrics["cumulative_alpha"] > 0
    assert metrics["win_rate"] >= 80.0
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics

def test_simulate_trades_portfolio():
    trades = [
        {
            "ticker": "NVDA",
            "disclosure_date": datetime.date(2024, 7, 2),
            "amount_midpoint": 3000000.0,
            "return_90d": 32.6,
            "benchmark_return_90d": 5.8
        },
        {
            "ticker": "LMT",
            "disclosure_date": datetime.date(2024, 8, 15),
            "amount_midpoint": 175000.0,
            "return_90d": 24.5,
            "benchmark_return_90d": 4.2
        },
        {
            "ticker": "BA",
            "disclosure_date": datetime.date(2024, 9, 18),
            "amount_midpoint": 75000.0,
            "return_90d": -11.4,
            "benchmark_return_90d": 4.0
        }
    ]
    sim = simulate_trades_portfolio(trades, initial_capital=100000.0)
    assert sim["initial_capital"] == 100000.0
    assert len(sim["timeline"]) == 3
    assert sim["metrics"]["cumulative_return"] > 0
    assert "portfolio_curve" in sim
    assert "benchmark_curve" in sim

def test_simultaneous_trades_compounding_invariance():
    # 3 concurrent trades of 10% on the same date should not compound into 33.1%
    same_day_trades = [
        {"ticker": "AAPL", "disclosure_date": datetime.date(2024, 6, 1), "return_90d": 10.0, "benchmark_return_90d": 3.0},
        {"ticker": "MSFT", "disclosure_date": datetime.date(2024, 6, 1), "return_90d": 10.0, "benchmark_return_90d": 3.0},
        {"ticker": "GOOG", "disclosure_date": datetime.date(2024, 6, 1), "return_90d": 10.0, "benchmark_return_90d": 3.0}
    ]
    sim = simulate_trades_portfolio(same_day_trades, initial_capital=100000.0)
    assert sim["final_value"] == 110000.0
    assert sim["metrics"]["cumulative_return"] == 10.0

def test_falsy_zero_return_preserved():
    # 0.0% breakeven trade should not falsify to 5.0%
    zero_trades = [
        {"ticker": "FLAT", "disclosure_date": datetime.date(2024, 6, 1), "return_90d": 0.0, "benchmark_return_90d": 0.0}
    ]
    sim = simulate_trades_portfolio(zero_trades, initial_capital=100000.0)
    assert sim["metrics"]["cumulative_return"] == 0.0
    assert sim["metrics"]["cumulative_benchmark"] == 0.0

def test_zero_variance_sharpe_ratio():
    metrics = calculate_portfolio_metrics([-0.05], [0.01])
    assert metrics["sharpe_ratio"] == 0.0  # Not positive 1.5

def test_empty_trades_simulation():
    sim = simulate_trades_portfolio([], initial_capital=50000.0)
    assert sim["initial_capital"] == 50000.0
    assert sim["final_value"] == 50000.0
    assert sim["final_benchmark_value"] == 50000.0
    assert sim["timeline"] == []
    assert len(sim["portfolio_curve"]) == 1
    assert len(sim["benchmark_curve"]) == 1
    assert sim["metrics"]["cumulative_return"] == 0.0

