from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SoftDeleteMixin


class Organization(Base, SoftDeleteMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    org_type: Mapped[str] = mapped_column(String(32), default="brokerage", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    api_keys = relationship("APIKey", back_populates="organization", cascade="all, delete-orphan")
    listings = relationship("Listing", back_populates="organization", cascade="all, delete-orphan")
    signal_events = relationship("SignalEvent", back_populates="organization", cascade="all, delete-orphan")
    listing_scores = relationship("ListingScore", back_populates="organization", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="organization", cascade="all, delete-orphan")
    usage_logs = relationship("APIUsageLog", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")
