from datetime import date
from typing import Optional
from sqlalchemy import String, Date, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioseeder.database import Base


class CatalystEvent(Base):
    __tablename__ = "catalyst_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_id: Mapped[int] = mapped_column(ForeignKey("drug_candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    trial_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clinical_trials.id", ondelete="SET NULL"), nullable=True, index=True)

    catalyst_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # PDUFA, Phase 1/2/3 Readout, AdCom, CRL, 510(k), Special Designation
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    date_precision: Mapped[str] = mapped_column(String(20), default="EXACT")  # EXACT, MONTH, QUARTER, HALF_YEAR
    status: Mapped[str] = mapped_column(String(50), default="UPCOMING", index=True)  # UPCOMING, COMPLETED, DELAYED, CANCELLED
    outcome: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, POSITIVE, NEGATIVE, NEUTRAL
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="catalysts")
    drug: Mapped["DrugCandidate"] = relationship("DrugCandidate", back_populates="catalysts")
    trial: Mapped[Optional["ClinicalTrial"]] = relationship("ClinicalTrial", back_populates="catalysts")
    score: Mapped[Optional["BioAlphaScore"]] = relationship("BioAlphaScore", back_populates="catalyst", uselist=False, cascade="all, delete-orphan", lazy="selectin")
