from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SoftDeleteMixin


class Listing(Base, SoftDeleteMixin):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    address: Mapped[str] = mapped_column(String(255))
    mls_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    property_type: Mapped[str] = mapped_column(String(32), default="single_family", index=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    zip_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    list_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    bedrooms: Mapped[int | None] = mapped_column(nullable=True)
    bathrooms: Mapped[float | None] = mapped_column(nullable=True)
    sqft: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="listings")
    signal_events = relationship("SignalEvent", back_populates="listing", cascade="all, delete-orphan")
    scores = relationship("ListingScore", back_populates="listing", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="listing", cascade="all, delete-orphan")
