from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SoftDeleteMixin


class SignalEvent(Base, SoftDeleteMixin):
    __tablename__ = "signal_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    signal_type: Mapped[str] = mapped_column(String(64), index=True)
    signal_value: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    metadata_json: Mapped[str | None] = mapped_column(String, nullable=True)

    organization = relationship("Organization", back_populates="signal_events")
    listing = relationship("Listing", back_populates="signal_events")
