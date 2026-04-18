from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthContext, ensure_org_admin, ensure_organization_access, verify_api_key
from app.models import APIKey, APIUsageLog, AuditEvent, Organization
from app.schemas.auth import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyRead,
    APIKeyRevokeResponse,
    APIKeyRotate,
    APIUsageLogRead,
    AuditEventRead,
    OrganizationCreate,
    OrganizationRead,
)
from app.services.auth_service import (
    create_api_key,
    create_organization,
    get_org_usage_summary,
    log_audit_event,
    restore_organization_tree,
    revoke_api_key,
    rotate_api_key,
    soft_delete_organization_tree,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/organizations", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_org(payload: OrganizationCreate, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    if not auth.is_bootstrap:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap key required")
    try:
        org = create_organization(db, org_id=payload.id, name=payload.name, org_type=payload.org_type)
        log_audit_event(db, organization_id=org.id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="organization.create", resource_type="organization", resource_id=org.id, details={"name": org.name, "org_type": org.org_type})
        db.commit()
        db.refresh(org)
        return org
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/organizations", response_model=list[OrganizationRead])
def list_orgs(include_deleted: bool = False, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    stmt = select(Organization)
    if auth.key_type == "organization":
        stmt = stmt.where(Organization.id == auth.organization_id)
    if not include_deleted:
        stmt = stmt.where(Organization.deleted_at.is_(None))
    return db.scalars(stmt.order_by(Organization.created_at.desc())).all()


@router.delete("/organizations/{organization_id}", response_model=OrganizationRead)
def delete_org(organization_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    ensure_org_admin(auth, organization_id)
    org = db.scalar(select(Organization).where(Organization.id == organization_id, Organization.deleted_at.is_(None)))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    soft_delete_organization_tree(db, org)
    log_audit_event(db, organization_id=organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="organization.delete", resource_type="organization", resource_id=organization_id)
    db.commit()
    db.refresh(org)
    return org


@router.post("/organizations/{organization_id}/restore", response_model=OrganizationRead)
def restore_org(organization_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    ensure_org_admin(auth, organization_id)
    org = db.scalar(select(Organization).where(Organization.id == organization_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    restore_organization_tree(db, org)
    log_audit_event(db, organization_id=organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="organization.restore", resource_type="organization", resource_id=organization_id)
    db.commit()
    db.refresh(org)
    return org


@router.post("/api-keys", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
def create_org_api_key(payload: APIKeyCreate, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    if auth.key_type == "organization":
        ensure_org_admin(auth, payload.organization_id)
    try:
        api_key, raw_key = create_api_key(
            db,
            organization_id=payload.organization_id,
            name=payload.name,
            role=payload.role,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            expires_at=payload.expires_at,
        )
        log_audit_event(db, organization_id=payload.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="api_key.create", resource_type="api_key", resource_id=api_key.id, details={"name": api_key.name, "role": api_key.role, "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None})
        db.commit()
        db.refresh(api_key)
        return APIKeyCreated.model_validate({**api_key.__dict__, "api_key": raw_key})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/organizations/{organization_id}/api-keys", response_model=list[APIKeyRead])
def list_org_api_keys(organization_id: str, include_deleted: bool = False, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    ensure_organization_access(auth, organization_id)
    stmt = select(APIKey).where(APIKey.organization_id == organization_id)
    if not include_deleted:
        stmt = stmt.where(APIKey.deleted_at.is_(None))
    return db.scalars(stmt.order_by(APIKey.created_at.desc())).all()


@router.post("/api-keys/{api_key_id}/revoke", response_model=APIKeyRevokeResponse)
def revoke_org_api_key(api_key_id: str, reason: str | None = None, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    api_key = db.scalar(select(APIKey).where(APIKey.id == api_key_id))
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    ensure_org_admin(auth, api_key.organization_id)

    revoke_api_key(db, api_key, reason=reason)
    log_audit_event(db, organization_id=api_key.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="api_key.revoke", resource_type="api_key", resource_id=api_key.id, details={"reason": api_key.revoked_reason})
    db.commit()
    db.refresh(api_key)
    return api_key


@router.post("/api-keys/{api_key_id}/rotate", response_model=APIKeyCreated)
def rotate_org_api_key(api_key_id: str, payload: APIKeyRotate, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    api_key = db.scalar(select(APIKey).where(APIKey.id == api_key_id))
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    ensure_org_admin(auth, api_key.organization_id)

    new_key, raw_key = rotate_api_key(
        db,
        api_key=api_key,
        new_name=payload.name,
        revoke_old_key=payload.revoke_old_key,
        role=payload.role,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        expires_at=payload.expires_at,
    )
    log_audit_event(db, organization_id=api_key.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="api_key.rotate", resource_type="api_key", resource_id=new_key.id, details={"rotated_from_key_id": api_key.id})
    db.commit()
    db.refresh(new_key)
    return APIKeyCreated.model_validate({**new_key.__dict__, "api_key": raw_key})


@router.get("/organizations/{organization_id}/usage-logs", response_model=list[APIUsageLogRead])
def get_usage_logs(organization_id: str, limit: int = 100, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    ensure_org_admin(auth, organization_id)
    stmt = (
        select(APIUsageLog)
        .where(APIUsageLog.organization_id == organization_id)
        .order_by(APIUsageLog.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    return db.scalars(stmt).all()


@router.get("/organizations/{organization_id}/usage-summary")
def get_usage_summary(organization_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    ensure_org_admin(auth, organization_id)
    return get_org_usage_summary(db, organization_id)


@router.get("/organizations/{organization_id}/audit-events", response_model=list[AuditEventRead])
def get_audit_events(organization_id: str, limit: int = 100, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    ensure_org_admin(auth, organization_id)
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    return db.scalars(stmt).all()
