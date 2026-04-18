from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthContext, ensure_org_admin, ensure_organization_access, resolve_organization_id, verify_api_key
from app.models import Listing, Organization
from app.schemas.listing import ListingCreate, ListingRead
from app.services.auth_service import log_audit_event, restore_listing_tree, soft_delete_listing_tree

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("", response_model=ListingRead, status_code=201)
def create_listing(payload: ListingCreate, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    existing = db.scalar(select(Listing).where(Listing.id == payload.id, Listing.deleted_at.is_(None)))
    if existing:
        raise HTTPException(status_code=409, detail="Listing already exists")

    organization_id = resolve_organization_id(auth, payload.organization_id)
    organization = db.scalar(select(Organization).where(Organization.id == organization_id, Organization.deleted_at.is_(None)))
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    listing_data = payload.model_dump(exclude={"organization_id"})
    listing = Listing(**listing_data, organization_id=organization_id)
    db.add(listing)
    log_audit_event(db, organization_id=organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="listing.create", resource_type="listing", resource_id=listing.id, details={"mls_id": listing.mls_id, "status": listing.status})
    db.commit()
    db.refresh(listing)
    return listing


@router.get("", response_model=list[ListingRead])
def list_listings(organization_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    scoped_org_id = resolve_organization_id(auth, organization_id)
    stmt = select(Listing).where(Listing.organization_id == scoped_org_id)
    if not include_deleted:
        stmt = stmt.where(Listing.deleted_at.is_(None))
    return db.scalars(stmt).all()


@router.get("/{listing_id}", response_model=ListingRead)
def get_listing(listing_id: str, include_deleted: bool = False, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    stmt = select(Listing).where(Listing.id == listing_id)
    if not include_deleted:
        stmt = stmt.where(Listing.deleted_at.is_(None))
    listing = db.scalar(stmt)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_organization_access(auth, listing.organization_id)
    return listing


@router.delete("/{listing_id}", response_model=ListingRead)
def delete_listing(listing_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_org_admin(auth, listing.organization_id)
    soft_delete_listing_tree(db, listing)
    log_audit_event(db, organization_id=listing.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="listing.delete", resource_type="listing", resource_id=listing.id)
    db.commit()
    db.refresh(listing)
    return listing


@router.post("/{listing_id}/restore", response_model=ListingRead)
def restore_listing(listing_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_org_admin(auth, listing.organization_id)
    org = db.scalar(select(Organization).where(Organization.id == listing.organization_id, Organization.deleted_at.is_(None)))
    if not org:
        raise HTTPException(status_code=409, detail="Cannot restore listing while organization is deleted")
    restore_listing_tree(db, listing)
    log_audit_event(db, organization_id=listing.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="listing.restore", resource_type="listing", resource_id=listing.id)
    db.commit()
    db.refresh(listing)
    return listing
