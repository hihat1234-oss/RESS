from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthContext, ensure_organization_access, verify_api_key
from app.models import Listing, Recommendation
from app.schemas.recommendation import RecommendationRead
from app.services.auth_service import log_audit_event
from app.services.recommendation_engine import generate_recommendations

router = APIRouter(prefix="/listings", tags=["recommendations"])


@router.post("/{listing_id}/recommendations/generate", response_model=list[RecommendationRead])
def generate_listing_recommendations(listing_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_organization_access(auth, listing.organization_id)

    try:
        recommendations = generate_recommendations(db, listing_id)
        log_audit_event(db, organization_id=listing.organization_id, api_key_id=auth.api_key_id, actor_type=auth.key_type, actor_name=auth.key_name, action="recommendation.generate", resource_type="recommendation", resource_id=listing_id)
        db.commit()
        return recommendations
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{listing_id}/recommendations", response_model=list[RecommendationRead])
def get_listing_recommendations(listing_id: str, db: Session = Depends(get_db), auth: AuthContext = Depends(verify_api_key)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    ensure_organization_access(auth, listing.organization_id)
    stmt = select(Recommendation).where(Recommendation.listing_id == listing_id, Recommendation.deleted_at.is_(None))
    return db.scalars(stmt).all()
