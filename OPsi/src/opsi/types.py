# src/opsi/types.py
"""Shared type definitions: raw chain, enriched contract, scores."""

from typing import Any, TypedDict


class RawContract(TypedDict):
    symbol: str
    expiry: str
    strike: float
    bid: float
    ask: float
    lastPrice: float
    volume: int
    openInterest: int


class EnrichedContract(RawContract):
    mid: float
    dte: int
    quoted: bool
    iv: float
    delta: float


class ScoreContext(TypedDict, total=False):
    iv_min: float
    iv_max: float
    trend: float
    iv_history: list[float]
    params: dict[str, Any]


class CoreScore(TypedDict):
    score: float
    ret_ann: float
    prob_otm: float
    liq: float
    iv_rank: float
    trend: float


class FinalScore(CoreScore):
    adj: float
    final: float
    notes: list[str]


class AcademicFlags(TypedDict, total=False):
    skew: bool
    term: bool
    jump: bool


class Position(TypedDict):
    """Strategy position: 1 leg (CSP/CC) or N legs (spread/condor)."""

    strategy: str
    legs: list[EnrichedContract]
    capital: float
    premium: float
