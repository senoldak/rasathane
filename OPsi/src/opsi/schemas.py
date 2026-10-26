# src/opsi/schemas.py
"""Pydantic v2 response schemas: single source for the API contract."""

from pydantic import BaseModel, Field


class ContractOut(BaseModel):
    symbol: str
    strike: float
    expiry: str
    strategy: str = "csp"
    bid: float | None = None
    ask: float | None = None
    score: float
    ret_ann: float
    prob_otm: float | None = None
    liq: float | None = None
    iv_rank: float | None = None
    trend: float | None = None
    adj: float | None = None
    details: str | None = None
    stock_score: float | None = None
    asset_type: str = "stock"
    max_profit: float | None = None
    max_loss: float | None = None
    breakeven: float | None = None
    legs: list[dict[str, float]] | None = None


class Top5Response(BaseModel):
    as_of: int | None = None
    as_of_is_latest: bool = True
    delayed: bool = True
    notice: str | None = Field(default=None, description="Veri gecikme bildirimi")
    items: list[ContractOut] = Field(default_factory=list)


class CandidatesResponse(BaseModel):
    items: list[ContractOut] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    last_scan_id: int | None = None
    last_scan_status: str | None = None
    last_scan_finished_at: str | None = None
    last_scan_candidates: int | None = None
    delayed: bool = True


class AttributionBucket(BaseModel):
    label: str
    n: int
    avg_return: float | None = None
    win_rate: float | None = None


class AttributionResponse(BaseModel):
    strategy: str | None = None
    buckets: list[AttributionBucket] = Field(default_factory=list)


class WatchlistIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    symbols: list[str] = Field(..., min_length=1)


class WatchlistOut(BaseModel):
    id: int
    name: str
    symbols: list[str]
    created_at: str
