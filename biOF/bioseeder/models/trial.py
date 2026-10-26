from datetime import date
from typing import Optional, Any
from sqlalchemy import String, Integer, Date, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioseeder.database import Base


class ClinicalTrial(Base):
    __tablename__ = "clinical_trials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    drug_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug_candidates.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Recruiting, Active, Completed, Terminated
    primary_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    study_type: Mapped[str] = mapped_column(String(50), default="Interventional")
    enrollment: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    brief_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    drug: Mapped[Optional["DrugCandidate"]] = relationship("DrugCandidate", back_populates="trials")
    catalysts: Mapped[list["CatalystEvent"]] = relationship("CatalystEvent", back_populates="trial")
