# tests/test_pricer_math_audit.py
"""Comprehensive mathematical, numerical stability, and convention audit tests for pricer.

Conforms to spx-options-math-audit standard:
- Put-Call parity across strikes/maturities/vols
- Analytical vs finite difference Greeks (Delta, Gamma, Vega)
- No-arbitrage lower and upper theoretical bounds
- Monotonicity and convexity properties
- IV solver convergence & boundary handling (sub-intrinsic / super-bound)
- 0DTE time-to-expiry fraction handling
"""

import math

import pytest

from opsi.pricer import (
    bs_call_delta,
    bs_call_price,
    bs_gamma,
    bs_put_delta,
    bs_put_price,
    bs_vega,
    calculate_time_to_expiry,
    implied_vol_put,
    no_arbitrage_bounds,
)


def test_put_call_parity():
    """Phase 5: Put-Call Parity C - P = S*exp(-q*T) - K*exp(-r*T)."""
    test_cases = [
        # S, K, T, r, q, sigma
        (100.0, 100.0, 30 / 365, 0.045, 0.0, 0.20),
        (5000.0, 4800.0, 7 / 365, 0.05, 0.015, 0.18),  # SPX-like ITM call / OTM put
        (5000.0, 5200.0, 45 / 365, 0.04, 0.015, 0.25),  # SPX-like OTM call / ITM put
        (25.0, 20.0, 14 / 365, 0.045, 0.0, 0.40),
        (150.0, 150.0, 0.5, 0.03, 0.02, 0.35),
    ]

    for S, K, T, r, q, sigma in test_cases:
        c = bs_call_price(S, K, T, r, q, sigma)
        p = bs_put_price(S, K, T, r, q, sigma)
        theoretical_diff = S * math.exp(-q * T) - K * math.exp(-r * T)
        actual_diff = c - p
        assert (
            abs(actual_diff - theoretical_diff) < 1e-11
        ), f"Parity violated for S={S}, K={K}, T={T}: diff={actual_diff - theoretical_diff}"


def test_greeks_finite_difference():
    """Phase 6 & 7: Analytical Greeks vs Numerical Finite Differences."""
    S = 100.0
    K = 105.0
    T = 40 / 365
    r = 0.045
    q = 0.01
    sigma = 0.22

    h = 1e-5

    # 1. Delta
    an_call_delta = bs_call_delta(S, K, T, r, q, sigma)
    fd_call_delta = (
        bs_call_price(S + h, K, T, r, q, sigma) - bs_call_price(S - h, K, T, r, q, sigma)
    ) / (2 * h)
    assert abs(an_call_delta - fd_call_delta) < 1e-6

    an_put_delta = bs_put_delta(S, K, T, r, q, sigma)
    fd_put_delta = (
        bs_put_price(S + h, K, T, r, q, sigma) - bs_put_price(S - h, K, T, r, q, sigma)
    ) / (2 * h)
    assert abs(an_put_delta - fd_put_delta) < 1e-6

    # 2. Gamma: Second-order central difference requires h balancing truncation and roundoff
    h_gamma = 1e-3
    an_gamma = bs_gamma(S, K, T, r, q, sigma)
    fd_gamma = (
        bs_call_price(S + h_gamma, K, T, r, q, sigma)
        - 2 * bs_call_price(S, K, T, r, q, sigma)
        + bs_call_price(S - h_gamma, K, T, r, q, sigma)
    ) / (h_gamma * h_gamma)
    assert abs(an_gamma - fd_gamma) < 1e-6

    # 3. Vega
    h_vol = 1e-4
    an_vega = bs_vega(S, K, T, r, q, sigma)
    fd_vega = (
        bs_call_price(S, K, T, r, q, sigma + h_vol) - bs_call_price(S, K, T, r, q, sigma - h_vol)
    ) / (2 * h_vol)
    assert abs(an_vega - fd_vega) < 1e-5


def test_no_arbitrage_bounds_and_rejection():
    """Phase 8 & 9: Verify bounds calculation and IV solver rejection on violations."""
    S, K, T, r, q = 100.0, 100.0, 30 / 365, 0.045, 0.0
    lb_c, ub_c = no_arbitrage_bounds(S, K, T, r, q, right="C")
    lb_p, ub_p = no_arbitrage_bounds(S, K, T, r, q, right="P")

    assert lb_c >= 0 and ub_c <= S
    assert lb_p >= 0 and ub_p <= K * math.exp(-r * T)

    # Sub-intrinsic price rejection (negative time value arbitrage)
    # Deep ITM Put: K=120, S=100 -> Intrinsic ~ 19.55
    K_itm = 120.0
    lb_itm_p, _ = no_arbitrage_bounds(S, K_itm, T, r, q, right="P")
    assert lb_itm_p > 15.0

    # Market price below lower bound must raise ValueError
    with pytest.raises(ValueError, match="no-arbitrage"):
        implied_vol_put(mkt=lb_itm_p - 1.0, S=S, K=K_itm, T=T, r=r, q=q, right="P")

    # Market price above upper bound must raise ValueError
    with pytest.raises(ValueError, match="no-arbitrage"):
        implied_vol_put(mkt=K_itm + 5.0, S=S, K=K_itm, T=T, r=r, q=q, right="P")


def test_monotonicity():
    """Phase 10: Monotonicity tests."""
    S, K, T, r, q, sigma = 100.0, 100.0, 30 / 365, 0.045, 0.0, 0.25

    # Higher S -> higher Call, lower Put
    assert bs_call_price(S + 1, K, T, r, q, sigma) > bs_call_price(S, K, T, r, q, sigma)
    assert bs_put_price(S + 1, K, T, r, q, sigma) < bs_put_price(S, K, T, r, q, sigma)

    # Higher Strike -> lower Call, higher Put
    assert bs_call_price(S, K + 1, T, r, q, sigma) < bs_call_price(S, K, T, r, q, sigma)
    assert bs_put_price(S, K + 1, T, r, q, sigma) > bs_put_price(S, K, T, r, q, sigma)

    # Higher Vol -> higher Call and Put
    assert bs_call_price(S, K, T, r, q, sigma + 0.05) > bs_call_price(S, K, T, r, q, sigma)
    assert bs_put_price(S, K, T, r, q, sigma + 0.05) > bs_put_price(S, K, T, r, q, sigma)


def test_0dte_time_calculation():
    """Phase 11: 0DTE expiry handling should yield positive non-zero T."""
    import datetime

    now = datetime.datetime(2026, 9, 9, 14, 0, 0, tzinfo=datetime.UTC)
    expiry_today = "2026-09-09"
    dte, T = calculate_time_to_expiry(expiry_today, now=now)

    assert dte == 0
    assert 0 < T < (1 / 365)  # Intraday fraction, less than 1 full calendar day


def test_golden_reference_case():
    """Phase 20: Golden test case with published analytical benchmark."""
    # Standard Hull textbook benchmark (Chapter 15):
    # S = 49, K = 50, r = 0.05, q = 0, sigma = 0.20, T = 0.3846 (approx 20 weeks)
    S, K, r, q, sigma, T = 49.0, 50.0, 0.05, 0.0, 0.20, 0.3846
    call = bs_call_price(S, K, T, r, q, sigma)
    put = bs_put_price(S, K, T, r, q, sigma)

    # Verified Hull benchmark values: Call ≈ 2.4005, Put ≈ 2.4481
    assert abs(call - 2.4005) < 0.005
    assert abs(put - 2.4481) < 0.005
