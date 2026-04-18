from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthContext, ensure_organization_access, verify_api_key
from app.models import Listing, SignalEvent
from app.schemas.signal_event import SignalEventBulkCreate, SignalEventCreate, SignalEventRead
from app.services.auth_service import log_audit_event

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("", response_model=SignalEventRead, status_code=201)
def create_signal(payload: SignalEventCreate, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == payload.listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_organization_access(auth, listing.organization_id)
    if db.scalar(select(SignalEvent).where(SignalEvent.id == payload.id, SignalEvent.deleted_at.is_(None))):
        raise HTTPException(status_code=409, detail="Signal already exists")

    signal_data = payload.model_dump(exclude={"organization_id"})
    signal = SignalEvent(**signal_data, organization_id=listing.organization_id)
    if signal.occurred_at is None:
        signal.occurred_at = datetime.utcnow()

    db.add(signal)
    log_audit_event(db, organization_id=listing.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="signal.create", resource_type="signal", resource_id=signal.id, details={"listing_id": listing.id, "signal_type": signal.signal_type})
    db.commit()
    db.refresh(signal)
    return signal


@router.post("/bulk", response_model=list[SignalEventRead], status_code=201)
def create_signals(payload: SignalEventBulkCreate, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    created: list[SignalEvent] = []
    org_id: str | None = None
    for event in payload.events:
        listing = db.scalar(select(Listing).where(Listing.id == event.listing_id, Listing.deleted_at.is_(None)))
        if not listing:
            raise HTTPException(status_code=404, detail=f"Listing {event.listing_id} not found")
        ensure_organization_access(auth, listing.organization_id)
        if db.scalar(select(SignalEvent).where(SignalEvent.id == event.id, SignalEvent.deleted_at.is_(None))):
            raise HTTPException(status_code=409, detail=f"Signal {event.id} already exists")
        signal = SignalEvent(**event.model_dump(exclude={"organization_id"}), organization_id=listing.organization_id)
        if signal.occurred_at is None:
            signal.occurred_at = datetime.utcnow()
        db.add(signal)
        created.append(signal)
        org_id = listing.organization_id

    log_audit_event(db, organization_id=org_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="signal.bulk_create", resource_type="signal", details={"count": len(created)})
    db.commit()
    for signal in created:
        db.refresh(signal)
    return created


@router.get("", response_model=list[SignalEventRead])
def list_signals(listing_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_organization_access(auth, listing.organization_id)
    stmt = select(SignalEvent).where(SignalEvent.listing_id == listing_id, SignalEvent.deleted_at.is_(None)).order_by(SignalEvent.occurred_at.desc())
    return db.scalars(stmt).all()
