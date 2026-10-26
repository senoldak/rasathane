from typing import List, Optional
from sqlalchemy import String, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioseeder.database import Base


class DrugCandidate(Base):
    __tablename__ = "drug_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    generic_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    brand_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    indication: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    therapeutic_area: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_tam: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in $M
    highest_phase: Mapped[str] = mapped_column(String(50), nullable=False)  # Preclinical, Phase 1, Phase 2, Phase 3, NDA/BLA, Approved
    mechanism_of_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="drugs")
    trials: Mapped[List["ClinicalTrial"]] = relationship("ClinicalTrial", back_populates="drug", cascade="all, delete-orphan", lazy="selectin")
    catalysts: Mapped[List["CatalystEvent"]] = relationship("CatalystEvent", back_populates="drug", cascade="all, delete-orphan", lazy="selectin")
