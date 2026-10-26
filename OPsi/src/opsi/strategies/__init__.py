# src/opsi/strategies/__init__.py
"""Strategy plugin registry: scan.py reads from here; adding a strategy suffices."""

from .base import Strategy
from .bull_put_spread import BullPutSpread
from .covered_call import CoveredCall
from .csp import CashSecuredPut
from .iron_condor import IronCondor

STRATEGIES: dict[str, Strategy] = {
    "csp": CashSecuredPut(),
    "covered_call": CoveredCall(),
    "bull_put_spread": BullPutSpread(),
    "iron_condor": IronCondor(),
}

__all__ = ["STRATEGIES", "Strategy"]
