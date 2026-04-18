from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    id: str | None = None
    name: str
    org_type: str = Field(default="brokerage")


class OrganizationRead(BaseModel):
    id: str
    name: str
    org_type: str
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    organization_id: str
    name: str = Field(default="default")
    role: str = Field(default="member")
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=10000)
    expires_at: datetime | None = None


class APIKeyRotate(BaseModel):
    name: str | None = None
    revoke_old_key: bool = True
    role: str | None = None
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=10000)
    expires_at: datetime | None = None


class APIKeyRead(BaseModel):
    id: str
    organization_id: str
    name: str
    role: str
    key_prefix: str
    is_active: bool
    usage_count: int
    rate_limit_per_minute: int
    rotated_from_key_id: str | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None = None
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class APIKeyCreated(APIKeyRead):
    api_key: str


class APIKeyRevokeResponse(BaseModel):
    id: str
    organization_id: str
    is_active: bool
    revoked_at: datetime | None
    revoked_reason: str | None = None

    model_config = {"from_attributes": True}


class APIUsageLogRead(BaseModel):
    id: str
    organization_id: str | None
    api_key_id: str | None
    key_type: str
    method: str
    path: str
    status_code: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditEventRead(BaseModel):
    id: str
    organization_id: str | None
    api_key_id: str | None
    actor_type: str
    actor_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
