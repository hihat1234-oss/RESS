from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SoftDeleteMixin


class ListingScore(Base, SoftDeleteMixin):
    __tablename__ = "listing_scores"

    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    demand_score: Mapped[float] = mapped_column(Float, default=0.0)
    momentum_score: Mapped[float] = mapped_column(Float, default=0.0)
    price_pressure_score: Mapped[float] = mapped_column(Float, default=0.0)
    benchmark_demand_score: Mapped[float] = mapped_column(Float, default=0.0)
    relative_demand_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    comparable_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="listing_scores")
    listing = relationship("Listing", back_populates="scores")
