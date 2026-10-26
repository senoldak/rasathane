# src/opsi/backtest/__init__.py
"""Backtest: live-accumulation attribution + BS payoff simulator."""

from .attribution import run_attribution
from .simulator import simulate_strategy

__all__ = ["run_attribution", "simulate_strategy"]
