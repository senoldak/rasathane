from datetime import datetime, timezone
from sqlalchemy import Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioseeder.database import Base


class BioAlphaScore(Base):
    __tablename__ = "bio_alpha_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    catalyst_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    composite_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)  # 0 to 100
    proximity_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0 to 100
    pos_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0 to 100
    asymmetry_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0 to 100
    dilution_hazard_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0 to 100
    smart_money_score: Mapped[float] = mapped_column(Float, default=50.0)  # 0 to 100

    dilution_flag: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # True if cash runway < 6 months
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    catalyst: Mapped["CatalystEvent"] = relationship("CatalystEvent", back_populates="score")
