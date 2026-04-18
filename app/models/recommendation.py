from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SoftDeleteMixin


class Recommendation(Base, SoftDeleteMixin):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    recommendation_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(1000))
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="recommendations")
    listing = relationship("Listing", back_populates="recommendations")
