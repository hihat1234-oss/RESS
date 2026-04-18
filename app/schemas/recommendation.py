from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    listing_id: str
    recommendation_type: str
    message: str
    priority: str
    created_at: datetime
    deleted_at: datetime | None = None
