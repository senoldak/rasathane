import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class FederalContractSchema(BaseModel):
    agency_name: str
    contract_id: str
    award_date: datetime.date
    award_amount: float
    days_between_trade_and_contract: int
    match_confidence_score: float

    model_config = ConfigDict(from_attributes=True)

class AlphaScoreSchema(BaseModel):
    conflict_score: float
    cluster_score: float
    winrate_score: float
    size_score: float
    asset_score: float
    decay_penalty: float
    composite_alpha_score: float
    rationale: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

class StockTradeResponse(BaseModel):
    id: int
    filing_id: str
    bioguide_id: str
    politician_name: Optional[str] = None
    party: Optional[str] = None
    state: Optional[str] = None
    chamber: Optional[str] = None
    ticker: str
    company_name: str
    asset_type: str
    transaction_type: str
    transaction_date: datetime.date
    disclosure_date: datetime.date
    amount_range_str: str
    amount_min: float
    amount_max: float
    amount_midpoint: float
    owner_type: str
    option_strike: Optional[float] = None
    option_expiration: Optional[datetime.date] = None
    filing_lag_days: int
    is_stock_act_violation: bool
    violation_severity: str
    price_at_transaction: Optional[float] = None
    price_at_disclosure: Optional[float] = None
    return_30d: Optional[float] = None
    return_90d: Optional[float] = None
    benchmark_return_90d: Optional[float] = None
    alpha_score: Optional[AlphaScoreSchema] = None
    contracts: List[FederalContractSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class PaginatedTradesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[StockTradeResponse]

class CommitteeMembershipSchema(BaseModel):
    committee_code: str
    committee_name: str
    subcommittee_name: Optional[str] = None
    role: str
    jurisdiction_keywords: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class PoliticianLeaderboardItem(BaseModel):
    bioguide_id: str
    first_name: str
    last_name: str
    chamber: str
    party: str
    state: str
    district: Optional[int] = None
    leadership_title: Optional[str] = None
    image_url: Optional[str] = None
    win_rate: float
    total_volume: float
    alpha_score: float
    total_trades_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class PoliticianDetailResponse(BaseModel):
    politician: PoliticianLeaderboardItem
    committees: List[CommitteeMembershipSchema]
    recent_trades: List[StockTradeResponse]
    sector_breakdown: Dict[str, float] = Field(default_factory=dict)
    win_rate_vs_spy: float

class BipartisanClusterResponse(BaseModel):
    ticker: str
    cluster_score: float
    signal_type: str
    start_date: datetime.date
    end_date: datetime.date
    democrat_count: int
    republican_count: int
    total_members: int
    trades: List[Dict[str, Any]]

class ConflictTradeResponse(BaseModel):
    trade: StockTradeResponse
    committee_name: str
    committee_role: str
    conflict_score: float
    rationale: str
    contracts: List[FederalContractSchema]

class ViolationItem(BaseModel):
    trade_id: int
    filing_id: str
    bioguide_id: str
    politician_name: str
    party: str
    chamber: str
    ticker: str
    transaction_date: datetime.date
    disclosure_date: datetime.date
    filing_lag_days: int
    days_overdue: int
    violation_severity: str
    estimated_statutory_fine: float
    doc_url: str

class ViolationsResponse(BaseModel):
    total_violations_count: int
    total_estimated_fines: float
    violations: List[ViolationItem]

class SimulationTimelineItem(BaseModel):
    date: str
    ticker: str
    trade_return: float
    benchmark_return: float
    portfolio_balance: float
    benchmark_balance: float

class SimulationMetrics(BaseModel):
    cumulative_return: float
    cumulative_benchmark: float
    cumulative_alpha: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float

class SimulationResponse(BaseModel):
    initial_capital: float
    final_value: float
    final_benchmark_value: float
    timeline: List[SimulationTimelineItem]
    portfolio_curve: List[Dict[str, Any]]
    benchmark_curve: List[Dict[str, Any]]
    metrics: SimulationMetrics

class WebhookRegisterRequest(BaseModel):
    webhook_url: str
    platform: str = "discord"  # 'discord', 'telegram', 'slack'
    min_score: int = 80

class WebhookRegisterResponse(BaseModel):
    status: str
    message: str
    webhook_url: str
    min_score: int
