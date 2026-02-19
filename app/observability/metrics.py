"""
Observability metrics for Level 2.

Tracks:
- Churn rate (% slots changed per reallocation)
- Coverage (% required sorties scheduled)
- Violation count
- Avg replan time
- Disruption event frequency
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import RosterVersion, DisruptionEvent


def get_metrics(db: Session, days: int = 7) -> dict:
    """
    Get observability metrics for the past N days.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Query roster versions
    versions = (
        db.query(RosterVersion)
        .filter(RosterVersion.created_at >= cutoff)
        .all()
    )
    
    # Query disruption events
    events = (
        db.query(DisruptionEvent)
        .filter(DisruptionEvent.created_at >= cutoff)
        .all()
    )
    
    if not versions:
        return {
            "period_days": days,
            "total_reallocations": 0,
            "avg_churn_rate": 0.0,
            "max_churn_rate": 0.0,
            "total_disruptions": 0,
            "disruption_types": {},
        }
    
    # Compute metrics
    churn_rates = [v.churn_rate for v in versions if v.churn_rate is not None]
    
    disruption_types = {}
    for event in events:
        disruption_types[event.event_type] = \
            disruption_types.get(event.event_type, 0) + 1
    
    return {
        "period_days": days,
        "total_reallocations": len(versions),
        "avg_churn_rate": sum(churn_rates) / len(churn_rates) if churn_rates else 0.0,
        "max_churn_rate": max(churn_rates) if churn_rates else 0.0,
        "min_churn_rate": min(churn_rates) if churn_rates else 0.0,
        "total_disruptions": len(events),
        "disruption_types": disruption_types,
        "reallocations_per_day": len(versions) / days,
    }


def get_coverage_metrics(roster: dict) -> dict:
    """
    Compute coverage metrics for a roster.
    """
    total_slots = sum(len(day["slots"]) for day in roster["roster"])
    
    go_slots = sum(
        1 for day in roster["roster"]
        for slot in day["slots"]
        if slot["dispatch_decision"] == "GO"
    )
    
    no_go_slots = sum(
        1 for day in roster["roster"]
        for slot in day["slots"]
        if slot["dispatch_decision"] == "NO_GO"
    )
    
    needs_review = sum(
        1 for day in roster["roster"]
        for slot in day["slots"]
        if slot["dispatch_decision"] == "NEEDS_REVIEW"
    )
    
    return {
        "total_slots": total_slots,
        "go_slots": go_slots,
        "no_go_slots": no_go_slots,
        "needs_review": needs_review,
        "coverage_rate": (go_slots / total_slots * 100) if total_slots > 0 else 0.0,
    }