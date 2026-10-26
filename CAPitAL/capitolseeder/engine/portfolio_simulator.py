import math
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from capitolseeder.db.models import StockTrade, Politician

def calculate_portfolio_metrics(
    returns: List[float],
    spy_returns: List[float],
    holding_days: int = 90
) -> Dict[str, float]:
    """
    Computes cumulative return, alpha spread, win rate, Sharpe ratio, and max drawdown.
    """
    if not returns:
        return {
            "cumulative_return": 0.0,
            "cumulative_benchmark": 0.0,
            "cumulative_alpha": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0
        }

    n = len(returns)
    port_equity = 1.0
    spy_equity = 1.0
    wins = 0

    peak = 1.0
    max_dd = 0.0

    for r, sr in zip(returns, spy_returns):
        port_equity *= (1.0 + r)
        spy_equity *= (1.0 + sr)
        if r >= sr:
            wins += 1
        
        if port_equity > peak:
            peak = port_equity
        dd = (peak - port_equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    cum_ret = round((port_equity - 1.0) * 100, 2)
    cum_spy = round((spy_equity - 1.0) * 100, 2)
    cum_alpha = round(cum_ret - cum_spy, 2)
    win_rate = round((wins / n) * 100, 2)

    # Sharpe ratio calculation with consistent trading-day annualization
    mean_ret = sum(returns) / n
    variance = sum((r - mean_ret) ** 2 for r in returns) / n if n > 1 else 0.0
    std_dev = math.sqrt(variance)
    if std_dev > 0:
        trading_days_per_period = 21 if holding_days <= 30 else 63
        annualization = math.sqrt(252 / trading_days_per_period)
        sharpe = round((mean_ret / (std_dev + 1e-6)) * annualization, 2)
    else:
        sharpe = 0.0

    return {
        "cumulative_return": cum_ret,
        "cumulative_benchmark": cum_spy,
        "cumulative_alpha": cum_alpha,
        "win_rate": win_rate,
        "sharpe_ratio": sharpe,
        "max_drawdown": round(max_dd * 100, 2)
    }

def simulate_trades_portfolio(
    trades: List[Dict[str, Any]],
    initial_capital: float = 100000.0,
    holding_days: int = 90
) -> Dict[str, Any]:
    """
    Simulates copycat trading starting at disclosure date.
    Trades occurring on the same date are grouped to prevent exponential compounding distortion.
    """
    if not trades:
        return {
            "initial_capital": initial_capital,
            "final_value": initial_capital,
            "final_benchmark_value": initial_capital,
            "timeline": [],
            "portfolio_curve": [{"date": datetime.date.today().isoformat(), "value": initial_capital}],
            "benchmark_curve": [{"date": datetime.date.today().isoformat(), "value": initial_capital}],
            "metrics": calculate_portfolio_metrics([], [], holding_days=holding_days)
        }

    # Sort trades by disclosure date
    sorted_trades = sorted(trades, key=lambda t: t["disclosure_date"])
    
    # Group trades by disclosure date for proportional allocation
    from collections import defaultdict
    date_trades = defaultdict(list)
    for t in sorted_trades:
        d = t["disclosure_date"]
        d_str = d.isoformat() if isinstance(d, datetime.date) else str(d)
        date_trades[d_str].append(t)

    current_val = initial_capital
    spy_val = initial_capital
    
    portfolio_curve = []
    benchmark_curve = []
    timeline = []
    period_returns_list = []
    period_spy_returns_list = []

    for d_str, day_group in date_trades.items():
        day_rets = []
        day_spy_rets = []

        for t in day_group:
            # Extract returns explicitly without falsy zero conversion
            ret_val = t.get("return_30d") if holding_days <= 30 else t.get("return_90d")
            if ret_val is None:
                ret_val = t.get("return_90d")
            if ret_val is None:
                ret_val = 5.0

            spy_val_trade = t.get("benchmark_return_30d") if holding_days <= 30 else t.get("benchmark_return_90d")
            if spy_val_trade is None:
                spy_val_trade = t.get("benchmark_return_90d")
            if spy_val_trade is None:
                spy_val_trade = 3.0

            r_pct = float(ret_val) / 100.0
            sr_pct = float(spy_val_trade) / 100.0

            day_rets.append(r_pct)
            day_spy_rets.append(sr_pct)

        # Average return across concurrent trades on this date
        avg_ret = sum(day_rets) / len(day_rets)
        avg_spy = sum(day_spy_rets) / len(day_spy_rets)

        period_returns_list.append(avg_ret)
        period_spy_returns_list.append(avg_spy)

        current_val *= (1.0 + avg_ret)
        spy_val *= (1.0 + avg_spy)

        portfolio_curve.append({"date": d_str, "value": round(current_val, 2)})
        benchmark_curve.append({"date": d_str, "value": round(spy_val, 2)})

        for i, t in enumerate(day_group):
            timeline.append({
                "date": d_str,
                "ticker": t["ticker"],
                "trade_return": round(day_rets[i] * 100, 2),
                "benchmark_return": round(day_spy_rets[i] * 100, 2),
                "portfolio_balance": round(current_val, 2),
                "benchmark_balance": round(spy_val, 2)
            })

    metrics = calculate_portfolio_metrics(period_returns_list, period_spy_returns_list, holding_days=holding_days)

    return {
        "initial_capital": initial_capital,
        "final_value": round(current_val, 2),
        "final_benchmark_value": round(spy_val, 2),
        "timeline": timeline,
        "portfolio_curve": portfolio_curve,
        "benchmark_curve": benchmark_curve,
        "metrics": metrics
    }

async def simulate_shadow_portfolio_db(
    session: AsyncSession,
    bioguide_id: Optional[str] = None,
    start_date: Optional[datetime.date] = None,
    initial_capital: float = 100000.0,
    holding_days: int = 90
) -> Dict[str, Any]:
    """
    Database query wrapper to execute backtest simulation.
    """
    stmt = select(StockTrade).order_by(StockTrade.disclosure_date.asc())
    if bioguide_id:
        stmt = stmt.where(StockTrade.bioguide_id == bioguide_id)
    if start_date:
        stmt = stmt.where(StockTrade.disclosure_date >= start_date)

    res = await session.execute(stmt)
    db_trades = res.scalars().all()

    trades_data = []
    for t in db_trades:
        trades_data.append({
            "ticker": t.ticker,
            "disclosure_date": t.disclosure_date,
            "amount_midpoint": t.amount_midpoint,
            "return_30d": t.return_30d if t.return_30d is not None else 2.0,
            "return_90d": t.return_90d if t.return_90d is not None else 5.0,
            "benchmark_return_90d": t.benchmark_return_90d if t.benchmark_return_90d is not None else 3.0
        })

    return simulate_trades_portfolio(trades_data, initial_capital, holding_days=holding_days)
