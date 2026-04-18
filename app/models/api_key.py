from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import SoftDeleteMixin


class APIKey(Base, SoftDeleteMixin):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="member", index=True)
    key_prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=120)
    rotated_from_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="api_keys")
    usage_logs = relationship("APIUsageLog", back_populates="api_key")
    audit_events = relationship("AuditEvent", back_populates="api_key")
    rotated_from = relationship("APIKey", remote_side=[id], uselist=False)
