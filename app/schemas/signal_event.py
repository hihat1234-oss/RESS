from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SignalEventBase(BaseModel):
    listing_id: str
    organization_id: str | None = None
    signal_type: str
    signal_value: float = 1.0
    source: str = "unknown"
    occurred_at: datetime | None = None
    metadata_json: str | None = None


class SignalEventCreate(SignalEventBase):
    id: str


class SignalEventBulkCreate(BaseModel):
    events: list[SignalEventCreate]


class SignalEventRead(SignalEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    occurred_at: datetime
    deleted_at: datetime | None = None
