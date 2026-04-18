from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ListingBase(BaseModel):
    address: str
    mls_id: str
    status: str = "active"
    property_type: str = "single_family"
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    list_price: Decimal
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None


class ListingCreate(ListingBase):
    id: str
    organization_id: str | None = None


class ListingRead(ListingBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    created_at: datetime
    deleted_at: datetime | None = None
