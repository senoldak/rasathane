# src/opsi/pricer.py
"""Black-Scholes pricer: put/call delta, price, greeks, and implied volatility."""

import datetime
import math

from scipy.stats import norm

from .types import EnrichedContract, RawContract


def _d1(S: float, K: float, T: float, r: float, q: float, sig: float) -> float:
    return (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))


def bs_put_delta(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Put delta (-1, 0); -0.5 on invalid input."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return -0.5
    d1 = _d1(S, K, T, r, q, sigma)
    return float(math.exp(-q * T) * (norm.cdf(d1) - 1.0))


def bs_call_delta(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Call delta (0, 1); 0.5 on invalid input."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.5
    d1 = _d1(S, K, T, r, q, sigma)
    return float(math.exp(-q * T) * norm.cdf(d1))


def bs_gamma(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Gamma (same for call and put; delta change per spot change)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, q, sigma)
    return float(math.exp(-q * T) * norm.pdf(d1) / (S * sigma * math.sqrt(T)))


def bs_vega(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Vega (same for call and put; premium change per 1.00 vol change)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, q, sigma)
    return float(S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T))


def bs_put_price(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Black-Scholes put price."""
    if T <= 0:
        return max(0.0, K - S)
    if sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, K * math.exp(-r * T) - S * math.exp(-q * T))
    d1 = _d1(S, K, T, r, q, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return float(K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1))


def bs_call_price(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Black-Scholes call price."""
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, S * math.exp(-q * T) - K * math.exp(-r * T))
    d1 = _d1(S, K, T, r, q, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return float(S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2))


def no_arbitrage_bounds(
    S: float, K: float, T: float, r: float, q: float, right: str = "P"
) -> tuple[float, float]:
    """Returns theoretical no-arbitrage bounds: (lower_bound, upper_bound)."""
    df_r = math.exp(-r * T)
    df_q = math.exp(-q * T)
    if right == "C":
        lb = max(0.0, S * df_q - K * df_r)
        ub = S * df_q
    else:
        lb = max(0.0, K * df_r - S * df_q)
        ub = K * df_r
    return lb, ub


def implied_vol_put(
    mkt: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    lo: float = 0.001,
    hi: float = 4.0,
    iters: int = 50,
    right: str = "P",
) -> float:
    """IV matching the market price (bisection); prices call when right='C'.

    Raises ValueError when theoretical no-arbitrage bounds are violated.
    """
    if T <= 0 or S <= 0 or K <= 0:
        raise ValueError("T, S and K must be positive")

    lb, ub = no_arbitrage_bounds(S, K, T, r, q, right=right)
    # Bounds check with tolerance
    if mkt < lb - 1e-7 or mkt > ub + 1e-7:
        raise ValueError(
            f"Piyasa fiyati no-arbitrage sinirlarini ihlal ediyor: mkt={mkt}, bounds=({lb:.4f}, {ub:.4f})"
        )

    price_fn = bs_call_price if right == "C" else bs_put_price
    p_lo = price_fn(S, K, T, r, q, lo)
    p_hi = price_fn(S, K, T, r, q, hi)

    if mkt <= p_lo:
        return lo
    if mkt >= p_hi:
        return hi

    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        p_mid = price_fn(S, K, T, r, q, mid)
        if p_mid > mkt:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def calculate_time_to_expiry(
    expiry_str: str,
    now: datetime.datetime | None = None,
) -> tuple[int, float]:
    """Returns DTE (days) and T (year fraction).

    For 0DTE (same-day expiry) uses intraday hour/minute fraction to avoid
    division by zero and artificial 1-day theta pressure.
    """
    if now is None:
        now = datetime.datetime.now(datetime.UTC)
    exp_date = datetime.date.fromisoformat(expiry_str)
    today = now.date()
    days = (exp_date - today).days

    if days > 0:
        dte = days
        T = days / 365.0
    elif days == 0:
        # 0DTE: time remaining until market close (16:00 ET / 20:00 UTC)
        dte = 0
        # Intraday fraction assuming a 20:00 UTC close
        close_time = datetime.datetime.combine(today, datetime.time(20, 0), tzinfo=datetime.UTC)
        remaining_seconds = max(60.0, (close_time - now).total_seconds())
        # Annualization: 365 * 86400 or session-hours based
        T = max(1e-5, remaining_seconds / (365.0 * 86400.0))
    else:
        dte = days
        T = 0.0

    return max(0, dte), max(1e-5, T)


def enrich(
    c: RawContract,
    S: float,
    r: float = 0.045,
    q: float = 0.0,
    right: str = "P",
    now: datetime.datetime | None = None,
) -> EnrichedContract:
    """Adds mid/dte/quoted/iv/delta to a raw contract.

    Without quotes (bid/ask=0) mid comes from lastPrice, quoted=False.
    Computes call delta when right="C".
    """
    dte, T = calculate_time_to_expiry(c["expiry"], now=now)
    bid = c.get("bid") or 0
    ask = c.get("ask") or 0
    if bid > 0 and ask >= bid:
        mid, quoted = 0.5 * (bid + ask), True
    else:
        mid, quoted = (c.get("lastPrice") or 0), False
    try:
        iv = implied_vol_put(mid, S, c["strike"], T, r, q, right=right) if mid > 0 else 0.30
    except Exception:
        iv = 0.30
    delta = (
        bs_put_delta(S, c["strike"], T, r, q, iv)
        if right != "C"
        else bs_call_delta(S, c["strike"], T, r, q, iv)
    )
    return {**c, "mid": mid, "dte": dte, "quoted": quoted, "iv": iv, "delta": delta}
