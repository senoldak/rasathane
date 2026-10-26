import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, ForeignKey, JSON, Text, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Politician(Base):
    __tablename__ = "politicians"
    
    bioguide_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chamber: Mapped[str] = mapped_column(String(10), nullable=False)  # 'House' or 'Senate'
    party: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    district: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    leadership_title: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_volume: Mapped[float] = mapped_column(Float, default=0.0)
    alpha_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    committees: Mapped[List["CommitteeMembership"]] = relationship("CommitteeMembership", back_populates="politician", cascade="all, delete-orphan")
    filings: Mapped[List["TransactionReport"]] = relationship("TransactionReport", back_populates="politician", cascade="all, delete-orphan")
    trades: Mapped[List["StockTrade"]] = relationship("StockTrade", back_populates="politician", cascade="all, delete-orphan")

class CommitteeMembership(Base):
    __tablename__ = "committee_memberships"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bioguide_id: Mapped[str] = mapped_column(String(10), ForeignKey("politicians.bioguide_id"), index=True)
    committee_code: Mapped[str] = mapped_column(String(16), nullable=False)
    committee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subcommittee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="Member")  # 'Chair', 'Ranking Member', 'Member'
    jurisdiction_keywords: Mapped[list] = mapped_column(JSON, default=list)
    
    politician: Mapped["Politician"] = relationship("Politician", back_populates="committees")

class TransactionReport(Base):
    __tablename__ = "transaction_reports"
    
    filing_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bioguide_id: Mapped[str] = mapped_column(String(10), ForeignKey("politicians.bioguide_id"), index=True)
    chamber: Mapped[str] = mapped_column(String(10), nullable=False)
    filing_type: Mapped[str] = mapped_column(String(16), default="PTR")
    filing_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    doc_url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    original_filing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ocr_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    politician: Mapped["Politician"] = relationship("Politician", back_populates="filings")
    trades: Mapped[List["StockTrade"]] = relationship("StockTrade", back_populates="filing", cascade="all, delete-orphan")

class StockTrade(Base):
    __tablename__ = "stock_trades"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filing_id: Mapped[str] = mapped_column(String(64), ForeignKey("transaction_reports.filing_id"), index=True)
    bioguide_id: Mapped[str] = mapped_column(String(10), ForeignKey("politicians.bioguide_id"), index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'Stock', 'Call_Option', 'Put_Option', 'Bond'
    transaction_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'Purchase', 'Sale', 'Exchange'
    transaction_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    disclosure_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    amount_range_str: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_min: Mapped[float] = mapped_column(Float, nullable=False)
    amount_max: Mapped[float] = mapped_column(Float, nullable=False)
    amount_midpoint: Mapped[float] = mapped_column(Float, nullable=False)
    owner_type: Mapped[str] = mapped_column(String(32), default="Self")  # 'Self', 'Spouse', 'Joint', 'Dependent Child'
    option_strike: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    option_expiration: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    filing_lag_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_stock_act_violation: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    violation_severity: Mapped[str] = mapped_column(String(16), default="None")
    price_at_transaction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_at_disclosure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_90d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    benchmark_return_90d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    politician: Mapped["Politician"] = relationship("Politician", back_populates="trades")
    filing: Mapped["TransactionReport"] = relationship("TransactionReport", back_populates="trades")
    contract_matches: Mapped[List["FederalContractMatch"]] = relationship("FederalContractMatch", back_populates="trade", cascade="all, delete-orphan")
    alpha_score: Mapped[Optional["CapitolAlphaScore"]] = relationship("CapitolAlphaScore", back_populates="trade", uselist=False, cascade="all, delete-orphan")

class FederalContractMatch(Base):
    __tablename__ = "federal_contract_matches"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_trades.id"), index=True)
    agency_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    award_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    award_amount: Mapped[float] = mapped_column(Float, nullable=False)
    days_between_trade_and_contract: Mapped[int] = mapped_column(Integer, nullable=False)
    match_confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    
    trade: Mapped["StockTrade"] = relationship("StockTrade", back_populates="contract_matches")

class CapitolAlphaScore(Base):
    __tablename__ = "capitol_alpha_scores"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_trades.id"), unique=True, index=True)
    conflict_score: Mapped[float] = mapped_column(Float, nullable=False)
    cluster_score: Mapped[float] = mapped_column(Float, nullable=False)
    winrate_score: Mapped[float] = mapped_column(Float, nullable=False)
    size_score: Mapped[float] = mapped_column(Float, nullable=False)
    asset_score: Mapped[float] = mapped_column(Float, nullable=False)
    decay_penalty: Mapped[float] = mapped_column(Float, nullable=False)
    composite_alpha_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    rationale: Mapped[dict] = mapped_column(JSON, default=dict)
    
    trade: Mapped["StockTrade"] = relationship("StockTrade", back_populates="alpha_score")

class WebhookSubscriber(Base):
    __tablename__ = "webhook_subscribers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webhook_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="discord")
    min_score: Mapped[int] = mapped_column(Integer, default=80)
    created_at: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
