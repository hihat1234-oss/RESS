from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import APIKey
from app.services.auth_service import get_api_key_record, get_request_count_in_window, record_api_key_usage

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


@dataclass
class AuthContext:
    key_type: str
    organization_id: str | None = None
    api_key_id: str | None = None
    key_name: str | None = None
    role: str | None = None

    @property
    def is_bootstrap(self) -> bool:
        return self.key_type == "bootstrap"


def verify_api_key(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> AuthContext:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

    db_key: APIKey | None = get_api_key_record(db, api_key)
    if db_key:
        recent_count = get_request_count_in_window(db, db_key.id, seconds=60)
        if recent_count >= db_key.rate_limit_per_minute:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        record_api_key_usage(db, db_key)
        auth = AuthContext(
            key_type="organization",
            organization_id=db_key.organization_id,
            api_key_id=db_key.id,
            key_name=db_key.name,
            role=db_key.role,
        )
        request.state.auth_context = auth
        return auth

    if settings.api_key and api_key == settings.api_key:
        auth = AuthContext(key_type="bootstrap", key_name="bootstrap", role="admin")
        request.state.auth_context = auth
        return auth

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def resolve_organization_id(auth: AuthContext, requested_organization_id: str | None = None) -> str:
    if auth.is_bootstrap:
        if not requested_organization_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="organization_id is required for bootstrap requests")
        return requested_organization_id

    if requested_organization_id and requested_organization_id != auth.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for that organization")

    if not auth.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context missing")

    return auth.organization_id


def ensure_organization_access(auth: AuthContext, organization_id: str) -> None:
    if auth.is_bootstrap:
        return
    if auth.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for that organization")


def ensure_org_admin(auth: AuthContext, organization_id: str | None = None) -> None:
    if auth.is_bootstrap:
        return
    if organization_id and auth.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for that organization")
    if auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin role required")
