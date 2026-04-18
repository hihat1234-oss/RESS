from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ListingScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    listing_id: str
    organization_id: str
    demand_score: float
    momentum_score: float
    price_pressure_score: float
    benchmark_demand_score: float
    relative_demand_ratio: float
    comparable_count: int
    updated_at: datetime
    deleted_at: datetime | None = None
