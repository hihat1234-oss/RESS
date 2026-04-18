from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class APIUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True, index=True)
    key_type: Mapped[str] = mapped_column(String(32), index=True)
    method: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(String(255), index=True)
    status_code: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    organization = relationship("Organization", back_populates="usage_logs")
    api_key = relationship("APIKey", back_populates="usage_logs")
