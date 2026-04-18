from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Listing, ListingScore, Recommendation


def generate_recommendations(db: Session, listing_id: str) -> list[Recommendation]:
    score = db.scalar(select(ListingScore).where(ListingScore.listing_id == listing_id, ListingScore.deleted_at.is_(None)))
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not score:
        raise ValueError("Score must be calculated before recommendations can be generated")
    if not listing:
        raise ValueError("Listing must exist before recommendations can be generated")

    db.execute(delete(Recommendation).where(Recommendation.listing_id == listing_id))

    recommendations: list[Recommendation] = []
    now = datetime.utcnow()
    market_label = ", ".join(
        part for part in [listing.property_type.replace("_", " "), listing.zip_code or listing.city, listing.state] if part
    )
    market_context = (
        f"This score is benchmarked against {score.comparable_count} comparable {listing.property_type.replace('_', ' ')} listing(s)"
        f"{' in ' + market_label if market_label else ''}, with a market baseline demand score of {score.benchmark_demand_score:.2f}."
        if score.comparable_count > 0
        else f"This score is using a fallback market baseline because no comparables were available yet for the current {listing.property_type.replace('_', ' ')} segment."
    )

    if score.relative_demand_ratio >= 1.15 and score.momentum_score >= 70:
        recommendations.append(
            Recommendation(
                id=f"rec-{listing_id}-accelerate",
                organization_id=listing.organization_id,
                listing_id=listing_id,
                recommendation_type="marketing_scale",
                message=(
                    f"Demand is outperforming the market and momentum is rising. Hold price, concentrate exposure in high-intent channels, "
                    f"and tighten follow-up speed. {market_context}"
                ),
                priority="high",
                created_at=now,
            )
        )
    elif score.relative_demand_ratio < 0.9 and score.price_pressure_score > 60:
        recommendations.append(
            Recommendation(
                id=f"rec-{listing_id}-reposition",
                organization_id=listing.organization_id,
                listing_id=listing_id,
                recommendation_type="pricing_adjustment",
                message=(
                    f"This listing is underperforming its market cohort. Consider a 2-3% price correction, refreshed creative, or sharper targeting. "
                    f"{market_context}"
                ),
                priority="high",
                created_at=now,
            )
        )
    else:
        recommendations.append(
            Recommendation(
                id=f"rec-{listing_id}-optimize",
                organization_id=listing.organization_id,
                listing_id=listing_id,
                recommendation_type="monitor_and_optimize",
                message=(
                    f"Performance is near market pace but not clearly breaking out. Hold price, monitor signal velocity, and test channel-level optimizations. "
                    f"{market_context}"
                ),
                priority="medium",
                created_at=now,
            )
        )

    if score.price_pressure_score > 70:
        recommendations.append(
            Recommendation(
                id=f"rec-{listing_id}-pressure",
                organization_id=listing.organization_id,
                listing_id=listing_id,
                recommendation_type="price_pressure_alert",
                message=(
                    "Price pressure is elevated relative to both demand and market benchmarks. Review active competition, buyer objections, and listing presentation quality."
                ),
                priority="medium",
                created_at=now,
            )
        )

    db.add_all(recommendations)
    db.flush()
    return db.scalars(select(Recommendation).where(Recommendation.listing_id == listing_id, Recommendation.deleted_at.is_(None))).all()
