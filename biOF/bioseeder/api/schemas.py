from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScoreBreakdownSchema(BaseModel):
    proximity_score: float
    pos_score: float
    asymmetry_score: float
    dilution_hazard_score: float
    smart_money_score: float


class CatalystItemSchema(BaseModel):
    id: int
    ticker: str
    company_name: str
    exchange: str
    market_cap: Optional[float] = None
    cash_runway_months: Optional[float] = None
    drug_name: str
    generic_name: Optional[str] = None
    indication: str
    therapeutic_area: str
    phase: str
    catalyst_type: str
    target_date: date
    days_to_event: int
    date_precision: str
    status: str
    outcome: str
    details: Optional[str] = None
    bio_alpha_score: float
    dilution_flag: bool
    score_breakdown: ScoreBreakdownSchema


class CatalystListResponse(BaseModel):
    total: int
    items: List[CatalystItemSchema]


class ScreenerItemSchema(BaseModel):
    catalyst_id: int
    ticker: str
    company_name: str
    drug_name: str
    indication: str
    phase: str
    catalyst_type: str
    target_date: date
    days_to_event: int
    market_cap: Optional[float] = None
    cash_runway_months: Optional[float] = None
    composite_score: float
    proximity_score: float
    pos_score: float
    asymmetry_score: float
    dilution_hazard_score: float
    smart_money_score: float
    dilution_flag: bool


class ScreenerResponse(BaseModel):
    total: int
    items: List[ScreenerItemSchema]


class ClinicalTrialSchema(BaseModel):
    nct_id: str
    title: str
    phase: str
    status: str
    primary_completion_date: Optional[date] = None
    enrollment: Optional[int] = None


class DrugCandidateSchema(BaseModel):
    id: int
    code_name: str
    generic_name: Optional[str] = None
    brand_name: Optional[str] = None
    indication: str
    therapeutic_area: str
    highest_phase: str
    target_tam: Optional[float] = None
    mechanism_of_action: Optional[str] = None
    trials: List[ClinicalTrialSchema] = []


class CompanyDossierResponse(BaseModel):
    ticker: str
    name: str
    exchange: str
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    quarterly_burn_rate: Optional[float] = None
    cash_runway_months: Optional[float] = None
    float_shares: Optional[float] = None
    short_interest_pct: Optional[float] = None
    drugs: List[DrugCandidateSchema] = []
    catalysts: List[CatalystItemSchema] = []


class LiveFeedItemSchema(BaseModel):
    id: str
    timestamp: datetime
    category: str  # APPROVAL, CRL, ADCOM, TRIAL_UPDATE, 8K_FILING
    headline: str
    ticker: Optional[str] = None
    details: str
    sentiment: str  # POSITIVE, NEGATIVE, NEUTRAL


class LiveFeedResponse(BaseModel):
    feed: List[LiveFeedItemSchema]
