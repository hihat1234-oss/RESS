from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, ListingScore, SignalEvent


@dataclass
class WindowMetrics:
    views: float = 0.0
    saves: float = 0.0
    showings: float = 0.0
    return_visitors: float = 0.0
    shares: float = 0.0
    inquiries: float = 0.0


@dataclass
class ScoreComponents:
    demand_score: float
    momentum_score: float
    activity_total: float


FALLBACK_BENCHMARK = WindowMetrics(
    views=250,
    saves=14,
    showings=6,
    return_visitors=24,
    shares=6,
    inquiries=4,
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _aggregate_events(events: list[SignalEvent]) -> WindowMetrics:
    metrics = defaultdict(float)
    for event in events:
        signal_type = event.signal_type.lower()
        if signal_type in {"view", "save", "showing_request", "return_visitor", "share", "inquiry"}:
            metrics[signal_type] += event.signal_value

    return WindowMetrics(
        views=metrics["view"],
        saves=metrics["save"],
        showings=metrics["showing_request"],
        return_visitors=metrics["return_visitor"],
        shares=metrics["share"],
        inquiries=metrics["inquiry"],
    )


def _weighted_total(metrics: WindowMetrics) -> float:
    return (
        metrics.views * 0.20
        + metrics.saves * 0.25
        + metrics.showings * 0.30
        + metrics.return_visitors * 0.10
        + metrics.shares * 0.05
        + metrics.inquiries * 0.10
    )


def _score_from_metrics(current: WindowMetrics, benchmark: WindowMetrics) -> float:
    def normalized(value: float, baseline: float, floor: float) -> float:
        return _clamp(value / max(baseline, floor))

    normalized_views = normalized(current.views, benchmark.views, 100.0)
    normalized_saves = normalized(current.saves, benchmark.saves, 8.0)
    normalized_showings = normalized(current.showings, benchmark.showings, 4.0)
    normalized_return_visitors = normalized(current.return_visitors, benchmark.return_visitors, 12.0)
    normalized_shares = normalized(current.shares, benchmark.shares, 5.0)
    normalized_inquiries = normalized(current.inquiries, benchmark.inquiries, 3.0)

    return (
        normalized_views * 0.20
        + normalized_saves * 0.25
        + normalized_showings * 0.30
        + normalized_return_visitors * 0.10
        + normalized_shares * 0.05
        + normalized_inquiries * 0.10
    ) * 100


def _compute_window_components(events: list[SignalEvent], now: datetime) -> tuple[WindowMetrics, WindowMetrics]:
    current_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)

    current_events = [e for e in events if e.occurred_at >= current_start]
    previous_events = [e for e in events if previous_start <= e.occurred_at < current_start]
    return _aggregate_events(current_events), _aggregate_events(previous_events)


def _compute_relative_score(current: WindowMetrics, previous: WindowMetrics, benchmark: WindowMetrics) -> ScoreComponents:
    demand_score = _score_from_metrics(current, benchmark)

    previous_total = _weighted_total(previous)
    current_total = _weighted_total(current)

    if previous_total <= 0 and current_total > 0:
        momentum_score = 100.0
    elif previous_total <= 0:
        momentum_score = 0.0
    else:
        momentum_ratio = current_total / previous_total
        momentum_score = _clamp(momentum_ratio / 2.0) * 100

    return ScoreComponents(
        demand_score=round(demand_score, 2),
        momentum_score=round(momentum_score, 2),
        activity_total=current_total,
    )


def _price_band(price: float) -> tuple[float, float]:
    return price * 0.8, price * 1.2


def _sqft_band(sqft: int) -> tuple[float, float]:
    return sqft * 0.75, sqft * 1.25


def _match_market_segment(subject: Listing, candidate: Listing) -> bool:
    if subject.property_type != candidate.property_type:
        return False

    if subject.zip_code and candidate.zip_code:
        return subject.zip_code == candidate.zip_code

    if subject.city and candidate.city and subject.state and candidate.state:
        return (
            subject.city.strip().lower() == candidate.city.strip().lower()
            and subject.state.strip().lower() == candidate.state.strip().lower()
        )

    if subject.state and candidate.state:
        return subject.state.strip().lower() == candidate.state.strip().lower()

    return True


def _is_comparable(subject: Listing, candidate: Listing) -> bool:
    if candidate.id == subject.id:
        return False
    if candidate.status != subject.status:
        return False
    if not _match_market_segment(subject, candidate):
        return False

    if subject.bedrooms is not None and candidate.bedrooms is not None and abs(candidate.bedrooms - subject.bedrooms) > 1:
        return False
    if subject.bathrooms is not None and candidate.bathrooms is not None and abs(candidate.bathrooms - subject.bathrooms) > 1.0:
        return False
    if subject.sqft and candidate.sqft:
        low, high = _sqft_band(subject.sqft)
        if not (low <= candidate.sqft <= high):
            return False
    if subject.list_price and candidate.list_price:
        low, high = _price_band(float(subject.list_price))
        if not (low <= float(candidate.list_price) <= high):
            return False
    return True


def _get_comparable_listings(db: Session, listing: Listing) -> list[Listing]:
    stmt = select(Listing).where(
        Listing.organization_id == listing.organization_id,
        Listing.status == listing.status,
        Listing.property_type == listing.property_type,
        Listing.deleted_at.is_(None),
    )
    candidates = db.scalars(stmt).all()
    strict = [candidate for candidate in candidates if _is_comparable(listing, candidate)]
    if strict:
        return strict

    relaxed_candidates = [
        candidate
        for candidate in candidates
        if candidate.id != listing.id
        and candidate.status == listing.status
        and candidate.property_type == listing.property_type
    ]
    return relaxed_candidates[:25]


def _build_benchmark(db: Session, listing: Listing, now: datetime) -> tuple[WindowMetrics, float, int]:
    comparables = _get_comparable_listings(db, listing)
    if not comparables:
        return FALLBACK_BENCHMARK, 50.0, 0

    previous_start = now - timedelta(days=14)
    comp_metrics: list[WindowMetrics] = []
    comp_scores: list[float] = []

    for comp in comparables:
        comp_events = db.scalars(
            select(SignalEvent).where(
                SignalEvent.listing_id == comp.id,
                SignalEvent.occurred_at >= previous_start,
                SignalEvent.occurred_at <= now,
                SignalEvent.deleted_at.is_(None),
            )
        ).all()
        current, previous = _compute_window_components(comp_events, now)
        comp_metrics.append(current)
        component = _compute_relative_score(
            current=current,
            previous=previous,
            benchmark=FALLBACK_BENCHMARK,
        )
        comp_scores.append(component.demand_score)

    benchmark = WindowMetrics(
        views=mean([m.views for m in comp_metrics]) if comp_metrics else FALLBACK_BENCHMARK.views,
        saves=mean([m.saves for m in comp_metrics]) if comp_metrics else FALLBACK_BENCHMARK.saves,
        showings=mean([m.showings for m in comp_metrics]) if comp_metrics else FALLBACK_BENCHMARK.showings,
        return_visitors=mean([m.return_visitors for m in comp_metrics]) if comp_metrics else FALLBACK_BENCHMARK.return_visitors,
        shares=mean([m.shares for m in comp_metrics]) if comp_metrics else FALLBACK_BENCHMARK.shares,
        inquiries=mean([m.inquiries for m in comp_metrics]) if comp_metrics else FALLBACK_BENCHMARK.inquiries,
    )
    return benchmark, round(mean(comp_scores), 2) if comp_scores else 50.0, len(comparables)


def calculate_demand_score(db: Session, listing_id: str, now: datetime | None = None) -> ListingScore:
    now = now or datetime.utcnow()
    current_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)

    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.deleted_at.is_(None)))
    if not listing:
        raise ValueError(f"Listing {listing_id} not found")

    events = db.scalars(
        select(SignalEvent).where(
            SignalEvent.listing_id == listing_id,
            SignalEvent.occurred_at >= previous_start,
            SignalEvent.occurred_at <= now,
            SignalEvent.deleted_at.is_(None),
        )
    ).all()

    current_events = [e for e in events if e.occurred_at >= current_start]
    previous_events = [e for e in events if previous_start <= e.occurred_at < current_start]

    current = _aggregate_events(current_events)
    previous = _aggregate_events(previous_events)
    benchmark, benchmark_demand_score, comparable_count = _build_benchmark(db, listing, now)

    components = _compute_relative_score(current=current, previous=previous, benchmark=benchmark)
    relative_demand_ratio = components.demand_score / benchmark_demand_score if benchmark_demand_score > 0 else 1.0
    relative_demand_ratio = round(relative_demand_ratio, 2)

    price_pressure_score = 100.0 - (
        components.demand_score * 0.65
        + components.momentum_score * 0.15
        + min(relative_demand_ratio, 1.5) / 1.5 * 20.0
    )
    price_pressure_score = round(max(0.0, min(100.0, price_pressure_score)), 2)

    score = db.scalar(select(ListingScore).where(ListingScore.listing_id == listing_id))
    if not score:
        score = ListingScore(listing_id=listing_id, organization_id=listing.organization_id)
        db.add(score)

    score.demand_score = components.demand_score
    score.momentum_score = components.momentum_score
    score.price_pressure_score = price_pressure_score
    score.benchmark_demand_score = benchmark_demand_score
    score.relative_demand_ratio = relative_demand_ratio
    score.comparable_count = comparable_count
    score.updated_at = now
    db.flush()
    return score
