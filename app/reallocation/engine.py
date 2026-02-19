"""
Reallocation engine — handles disruptions and replans the roster.

Disruption types:
  1. WEATHER_UPDATE
  2. AIRCRAFT_UNSERVICEABLE
  3. INSTRUCTOR_UNAVAILABLE
  4. STUDENT_UNAVAILABLE

Strategy:
  1. Identify affected slots
  2. Preserve unaffected slots (minimize churn)
  3. Generate candidate reallocations for affected slots
  4. Validate constraints
  5. Return roster diff
"""
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass
import uuid


@dataclass
class DisruptionEvent:
    event_type: str
    entity_id: Optional[str] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    metadata: dict = None
    correlation_id: str = None
    
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())
        if self.metadata is None:
            self.metadata = {}


def identify_affected_slots(roster: dict, event: DisruptionEvent) -> list[dict]:
    """
    Find which slots are affected by this disruption event.
    Returns list of affected slot objects.
    """
    affected = []
    
    for day in roster["roster"]:
        day_date = date.fromisoformat(day["date"])
        
        for slot in day["slots"]:
            # Check if slot falls within disruption time window
            if event.from_time and event.to_time:
                slot_date = date.fromisoformat(slot["date"])
                if not (event.from_time.date() <= slot_date <= event.to_time.date()):
                    continue
            
            # Check based on event type
            if event.event_type == "WEATHER_UPDATE":
                # All FLIGHT slots affected by weather
                if slot["activity"] == "FLIGHT":
                    affected.append(slot)
            
            elif event.event_type == "AIRCRAFT_UNSERVICEABLE":
                if slot["resource_id"] == event.entity_id and slot["activity"] == "FLIGHT":
                    affected.append(slot)
            
            elif event.event_type == "INSTRUCTOR_UNAVAILABLE":
                if slot["instructor_id"] == event.entity_id:
                    affected.append(slot)
            
            elif event.event_type == "STUDENT_UNAVAILABLE":
                if slot["student_id"] == event.entity_id:
                    affected.append(slot)
    
    return affected


def compute_roster_diff(old_roster: dict, new_roster: dict) -> dict:
    """
    Compute diff between two rosters.
    Returns: {added: [...], removed: [...], modified: [...]}
    """
    old_slots = {s["slot_id"]: s for day in old_roster["roster"] for s in day["slots"]}
    new_slots = {s["slot_id"]: s for day in new_roster["roster"] for s in day["slots"]}
    
    added = [s for sid, s in new_slots.items() if sid not in old_slots]
    removed = [s for sid, s in old_slots.items() if sid not in new_slots]
    
    modified = []
    for sid in set(old_slots.keys()) & set(new_slots.keys()):
        old = old_slots[sid]
        new = new_slots[sid]
        
        # Check if any field changed
        changes = {}
        for key in ["activity", "student_id", "instructor_id", "resource_id", 
                    "sortie_type", "dispatch_decision"]:
            if old.get(key) != new.get(key):
                changes[key] = {"old": old.get(key), "new": new.get(key)}
        
        if changes:
            modified.append({
                "slot_id": sid,
                "changes": changes
            })
    
    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "total_changes": len(added) + len(removed) + len(modified),
    }


def compute_churn_rate(diff: dict, total_slots: int) -> float:
    """Churn rate = (changes / total slots) * 100"""
    if total_slots == 0:
        return 0.0
    return (diff["total_changes"] / total_slots) * 100


def reallocate_roster(
    current_roster: dict,
    event: DisruptionEvent,
    students: list[dict],
    instructors: list[dict],
    aircraft: list[dict],
    simulators: list[dict],
    time_slots: list[dict],
    weather_data: dict = None,
) -> dict:
    """
    Main reallocation function.
    
    Returns: {
        "new_roster": {...},
        "diff": {...},
        "affected_slots": [...],
        "churn_rate": 5.2,
        "correlation_id": "uuid"
    }
    """
    from app.scheduling.roster import generate_roster
    from app.weather.fetcher import get_weather_mock
    from app.dispatch.engine import check_dispatch
    from copy import deepcopy
    
    # Step 1: Identify affected slots
    affected = identify_affected_slots(current_roster, event)
    
    # Step 2: Apply disruption
    modified_roster = deepcopy(current_roster)
    
    if event.event_type == "WEATHER_UPDATE":
        # Re-dispatch all FLIGHT slots with new weather
        weather = weather_data or get_weather_mock(
            current_roster["base_icao"],
            event.metadata.get("weather_scenario", "good")
        )
        
        students_map = {s["id"]: s for s in students}
        sim_slots_used = {}
        
        for day in modified_roster["roster"]:
            updated_slots = []
            for slot in day["slots"]:
                if slot["activity"] == "FLIGHT":
                    student = students_map[slot["student_id"]]
                    updated = check_dispatch(slot, student, weather, simulators, sim_slots_used)
                    
                    if updated["activity"] == "SIM":
                        rid = updated["resource_id"]
                        sim_slots_used.setdefault(rid, {})
                        sim_slots_used[rid][slot["date"]] = \
                            sim_slots_used[rid].get(slot["date"], 0) + 1
                    
                    updated_slots.append(updated)
                else:
                    updated_slots.append(slot)
            
            day["slots"] = updated_slots
    
    elif event.event_type in ("AIRCRAFT_UNSERVICEABLE", "INSTRUCTOR_UNAVAILABLE", "STUDENT_UNAVAILABLE"):
        # Remove affected slots, mark as NEEDS_REVIEW
        for day in modified_roster["roster"]:
            for slot in day["slots"]:
                if slot in affected:
                    slot["dispatch_decision"] = "NEEDS_REVIEW"
                    slot["reasons"] = [f"{event.event_type}_DISRUPTION"]
                    slot["citations"] = ["rules:doc_dispatch#disruption"]
    
    # Step 3: Compute diff
    diff = compute_roster_diff(current_roster, modified_roster)
    total_slots = sum(len(day["slots"]) for day in current_roster["roster"])
    churn_rate = compute_churn_rate(diff, total_slots)
    
    return {
        "new_roster": modified_roster,
        "diff": diff,
        "affected_slots": affected,
        "churn_rate": churn_rate,
        "correlation_id": event.correlation_id,
        "event_type": event.event_type,
    }