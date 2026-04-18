from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthContext, ensure_organization_access, verify_api_key
from app.models import Listing, ListingScore
from app.schemas.score import ListingScoreRead
from app.services.auth_service import log_audit_event
from app.services.scoring_engine import calculate_demand_score

router = APIRouter(prefix="/listings", tags=["scores"])


@router.get("/{listing_id}/scores", response_model=ListingScoreRead)
def get_listing_score(listing_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_organization_access(auth, listing.organization_id)

    score = db.scalar(select(ListingScore).where(ListingScore.listing_id == listing_id, ListingScore.deleted_at.is_(None)))
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")
    return score


@router.post("/{listing_id}/recalculate", response_model=ListingScoreRead)
def recalculate_listing_score(listing_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_organization_access(auth, listing.organization_id)

    try:
        score = calculate_demand_score(db, listing_id)
        log_audit_event(db, organization_id=listing.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="score.recalculate", resource_type="listing_score", resource_id=listing_id)
        db.commit()
        db.refresh(score)
        return score
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
