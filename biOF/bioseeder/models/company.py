from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioseeder.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), default="NASDAQ")
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in $M
    enterprise_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in $M
    cash_and_equivalents: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in $M
    quarterly_burn_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in $M
    cash_runway_months: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in months
    float_shares: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in M shares
    short_interest_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # percentage
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    drugs: Mapped[List["DrugCandidate"]] = relationship("DrugCandidate", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    catalysts: Mapped[List["CatalystEvent"]] = relationship("CatalystEvent", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
