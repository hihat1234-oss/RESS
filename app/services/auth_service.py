from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import APIKey, APIUsageLog, AuditEvent, Listing, ListingScore, Organization, Recommendation, SignalEvent


API_KEY_PREFIX_LEN = 8


def utcnow() -> datetime:
    return datetime.utcnow()


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw_key = f"ress_{secrets.token_urlsafe(24)}"
    return raw_key, raw_key[:API_KEY_PREFIX_LEN], _hash_api_key(raw_key)


def create_organization(db: Session, *, org_id: str | None, name: str, org_type: str) -> Organization:
    existing = db.scalar(select(Organization).where(Organization.name == name, Organization.deleted_at.is_(None)))
    if existing:
        raise ValueError("Organization already exists")

    organization = Organization(
        id=org_id or f"org_{secrets.token_hex(8)}",
        name=name,
        org_type=org_type,
    )
    db.add(organization)
    db.flush()
    return organization


def create_api_key(
    db: Session, *, organization_id: str, name: str, role: str = "member",
    rate_limit_per_minute: int | None = None, rotated_from_key_id: str | None = None, expires_at: datetime | None = None
) -> tuple[APIKey, str]:
    organization = db.scalar(
        select(Organization).where(Organization.id == organization_id, Organization.deleted_at.is_(None))
    )
    if not organization:
        raise ValueError("Organization not found")

    raw_key, key_prefix, key_hash = generate_api_key()
    api_key = APIKey(
        id=f"key_{secrets.token_hex(8)}",
        organization_id=organization_id,
        name=name,
        role=role,
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
        rate_limit_per_minute=rate_limit_per_minute or settings.default_rate_limit_per_minute,
        rotated_from_key_id=rotated_from_key_id,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.flush()
    return api_key, raw_key


def get_api_key_record(db: Session, raw_key: str) -> APIKey | None:
    key_hash = _hash_api_key(raw_key)
    candidate = db.scalar(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.is_active.is_(True),
            APIKey.deleted_at.is_(None),
            APIKey.revoked_at.is_(None),
        )
    )
    if not candidate:
        return None
    if candidate.expires_at and candidate.expires_at <= utcnow():
        revoke_api_key(db, candidate, reason="expired", soft_delete=False)
        db.commit()
        return None
    if not hmac.compare_digest(candidate.key_hash, key_hash):
        return None
    return candidate


def record_api_key_usage(db: Session, api_key: APIKey) -> APIKey:
    api_key.usage_count += 1
    api_key.last_used_at = utcnow()
    db.add(api_key)
    db.flush()
    return api_key


def get_request_count_in_window(db: Session, api_key_id: str, *, seconds: int = 60) -> int:
    window_start = utcnow() - timedelta(seconds=seconds)
    return db.scalar(
        select(func.count(APIUsageLog.id)).where(
            APIUsageLog.api_key_id == api_key_id,
            APIUsageLog.created_at >= window_start,
        )
    ) or 0


def revoke_api_key(db: Session, api_key: APIKey, reason: str | None = None, soft_delete: bool = True) -> APIKey:
    now = utcnow()
    api_key.is_active = False
    api_key.revoked_at = now
    api_key.revoked_reason = reason or "revoked"
    if soft_delete:
        api_key.deleted_at = now
    db.add(api_key)
    db.flush()
    return api_key


def rotate_api_key(
    db: Session,
    *,
    api_key: APIKey,
    new_name: str | None = None,
    revoke_old_key: bool = True,
    role: str | None = None,
    rate_limit_per_minute: int | None = None,
    expires_at: datetime | None = None,
) -> tuple[APIKey, str]:
    new_key, raw_key = create_api_key(
        db,
        organization_id=api_key.organization_id,
        name=new_name or api_key.name,
        role=role or api_key.role,
        rate_limit_per_minute=rate_limit_per_minute or api_key.rate_limit_per_minute,
        rotated_from_key_id=api_key.id,
        expires_at=expires_at if expires_at is not None else api_key.expires_at,
    )
    if revoke_old_key:
        revoke_api_key(db, api_key, reason=f"rotated_to:{new_key.id}")
    db.flush()
    return new_key, raw_key


def log_api_usage(
    db: Session,
    *,
    organization_id: str | None,
    api_key_id: str | None,
    key_type: str,
    method: str,
    path: str,
    status_code: int,
) -> APIUsageLog:
    usage_log = APIUsageLog(
        id=f"ulog_{secrets.token_hex(8)}",
        organization_id=organization_id,
        api_key_id=api_key_id,
        key_type=key_type,
        method=method,
        path=path,
        status_code=status_code,
        created_at=utcnow(),
    )
    db.add(usage_log)
    db.flush()
    return usage_log


def log_audit_event(
    db: Session,
    *,
    organization_id: str | None,
    api_key_id: str | None,
    actor_type: str,
    actor_name: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        id=f"audit_{secrets.token_hex(8)}",
        organization_id=organization_id,
        api_key_id=api_key_id,
        actor_type=actor_type,
        actor_name=actor_name,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=json.dumps(details or {}, sort_keys=True),
        created_at=utcnow(),
    )
    db.add(event)
    db.flush()
    return event


def soft_delete_listing_tree(db: Session, listing: Listing) -> Listing:
    now = utcnow()
    listing.deleted_at = now
    for signal in db.scalars(
        select(SignalEvent).where(SignalEvent.listing_id == listing.id, SignalEvent.deleted_at.is_(None))
    ).all():
        signal.deleted_at = now
        db.add(signal)

    score = db.scalar(
        select(ListingScore).where(ListingScore.listing_id == listing.id, ListingScore.deleted_at.is_(None))
    )
    if score:
        score.deleted_at = now
        db.add(score)

    for rec in db.scalars(
        select(Recommendation).where(Recommendation.listing_id == listing.id, Recommendation.deleted_at.is_(None))
    ).all():
        rec.deleted_at = now
        db.add(rec)

    db.add(listing)
    db.flush()
    return listing


def restore_listing_tree(db: Session, listing: Listing) -> Listing:
    listing.deleted_at = None
    for signal in db.scalars(select(SignalEvent).where(SignalEvent.listing_id == listing.id)).all():
        signal.deleted_at = None
        db.add(signal)

    score = db.scalar(select(ListingScore).where(ListingScore.listing_id == listing.id))
    if score:
        score.deleted_at = None
        db.add(score)

    for rec in db.scalars(select(Recommendation).where(Recommendation.listing_id == listing.id)).all():
        rec.deleted_at = None
        db.add(rec)

    db.add(listing)
    db.flush()
    return listing


def soft_delete_organization_tree(db: Session, organization: Organization) -> Organization:
    now = utcnow()
    organization.deleted_at = now

    for key in db.scalars(select(APIKey).where(APIKey.organization_id == organization.id, APIKey.deleted_at.is_(None))).all():
        key.is_active = False
        key.revoked_at = now
        key.revoked_reason = "organization_deleted"
        key.deleted_at = now
        db.add(key)

    for listing in db.scalars(
        select(Listing).where(Listing.organization_id == organization.id, Listing.deleted_at.is_(None))
    ).all():
        soft_delete_listing_tree(db, listing)

    db.add(organization)
    db.flush()
    return organization


def restore_organization_tree(db: Session, organization: Organization) -> Organization:
    organization.deleted_at = None
    for listing in db.scalars(select(Listing).where(Listing.organization_id == organization.id)).all():
        restore_listing_tree(db, listing)
    db.add(organization)
    db.flush()
    return organization


def get_org_usage_summary(db: Session, organization_id: str) -> dict:
    total_requests = db.scalar(
        select(func.count(APIUsageLog.id)).where(APIUsageLog.organization_id == organization_id)
    ) or 0
    active_keys = db.scalar(
        select(func.count(APIKey.id)).where(
            APIKey.organization_id == organization_id,
            APIKey.is_active.is_(True),
            APIKey.deleted_at.is_(None),
        )
    ) or 0
    listings = db.scalar(
        select(func.count(Listing.id)).where(Listing.organization_id == organization_id, Listing.deleted_at.is_(None))
    ) or 0
    return {
        "organization_id": organization_id,
        "total_requests": total_requests,
        "active_keys": active_keys,
        "active_listings": listings,
    }
