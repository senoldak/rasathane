# src/opsi/strategies/_shared.py
"""Shared stock score: used by all 4 strategy plugins."""

from typing import Any, cast


def stock_score_shared(snapshot: dict[str, object]) -> float:
    """Liquidity 40 + spread 20 + earnings 20 + IV regime 20 (neutral placeholder)."""
    vol = float(cast(Any, snapshot.get("put_volume", 0)) or 0)
    oi = float(cast(Any, snapshot.get("put_oi", 0)) or 0)
    liq = min((vol / 2000 + oi / 10000) / 2, 1.0)
    spread = float(cast(Any, snapshot.get("spread_sample", 1.0)) or 0.0)
    spread_term = max(0.0, 1.0 - spread * 10)
    ed = snapshot.get("earnings_days")
    earn = (
        0.0
        if (isinstance(ed, int) and ed < 7)
        else (0.5 if isinstance(ed, int) and ed < 14 else 1.0)
    )
    stale = 1.0 if int(cast(Any, snapshot.get("stale_flag", 0)) or 0) == 0 else 0.0
    return 100 * (0.4 * liq + 0.2 * spread_term + 0.2 * earn + 0.2 * stale)
