# src/opsi/backtest/simulator.py
"""BS payoff simulator: past stock price series + theoretical premium for strategy returns.

Under free-data constraints this gives a theoretical upper bound: on each date
the BS premium uses a fixed sigma instead of that day's IV, and the position
is closed at expiry.
"""

from ..pricer import bs_call_price, bs_put_price
from ..strategies import STRATEGIES


def simulate_strategy(
    symbol: str,
    strategy: str,
    closes: list[tuple[str, float]],
    strike: float,
    dte: int = 30,
    sigma: float = 0.3,
    r: float = 0.045,
) -> dict[str, float]:
    """Opens the strategy each day, closes at expiry; returns a return summary."""
    strat = STRATEGIES[strategy]
    rets: list[float] = []
    T = dte / 365.0
    n = len(closes)
    for i in range(n - dte):
        s0 = closes[i][1]
        s_t = closes[i + dte][1]
        if strategy == "csp":
            prem = bs_put_price(s0, strike, T, r, 0.0, sigma)
            legs = [{"strike": strike, "mid": prem}]
            capital = strike * 100
        elif strategy == "covered_call":
            prem = bs_call_price(s0, strike, T, r, 0.0, sigma)
            legs = [{"strike": strike, "mid": prem, "spot": s0}]
            capital = s0 * 100
        elif strategy == "bull_put_spread":
            width = 1.0
            prem_s = bs_put_price(s0, strike, T, r, 0.0, sigma)
            prem_l = bs_put_price(s0, strike - width, T, r, 0.0, sigma)
            legs = [
                {"strike": strike, "mid": prem_s},
                {"strike": strike - width, "mid": prem_l},
            ]
            capital = width * 100 - (prem_s - prem_l) * 100
        elif strategy == "iron_condor":
            width = 1.0
            prem_ps = bs_put_price(s0, strike, T, r, 0.0, sigma)
            prem_pl = bs_put_price(s0, strike - width, T, r, 0.0, sigma)
            prem_cs = bs_call_price(s0, strike + 2 * width, T, r, 0.0, sigma)
            prem_cl = bs_call_price(s0, strike + 3 * width, T, r, 0.0, sigma)
            legs = [
                {"strike": strike, "mid": prem_ps},
                {"strike": strike - width, "mid": prem_pl},
                {"strike": strike + 2 * width, "mid": prem_cs},
                {"strike": strike + 3 * width, "mid": prem_cl},
            ]
            credit = (prem_ps - prem_pl) + (prem_cs - prem_cl)
            capital = width * 100 - credit * 100
        else:
            raise ValueError(f"bilinmeyen strateji: {strategy}")
        if capital <= 0:
            continue
        rets.append(strat.settle(legs, s_t) / capital)
    if not rets:
        return {"n": 0, "avg_return": 0.0, "win_rate": 0.0, "max_loss": 0.0}
    return {
        "n": len(rets),
        "avg_return": sum(rets) / len(rets),
        "win_rate": sum(1 for x in rets if x > 0) / len(rets),
        "max_loss": min(rets),
    }
