"""
Business rules for sortie assignment.
Keeps roster.py clean — all rule logic lives here.
"""


def pick_sortie_type(student: dict) -> str:
    """
    Decide sortie type based on student stage + solo eligibility.
    Simple stage-based mapping for now.
    """
    stage = student.get("stage", "")
    solo_eligible = student.get("solo_eligible", False)

    if solo_eligible and stage.startswith("PPL-4"):
        return "SOLO"
    elif stage in ("PPL-3", "PPL-4"):
        return "NAV"
    elif stage == "PPL-2":
        return "CIRCUITS"
    else:
        return "CIRCUITS"   # default for PPL-1


def instructor_can_teach(instructor: dict, sortie_type: str) -> bool:
    """Instructor must have the sortie type in their ratings."""
    return sortie_type in instructor.get("ratings", [])


def needs_sim_instructor(sortie_type: str) -> bool:
    return sortie_type == "SIM_PROCEDURES"


def is_maintenance(aircraft: dict, day_name: str) -> bool:
    """
    Returns True if aircraft is on maintenance this day.
    Handles both status field and per-day 'MAINTENANCE' window.
    """
    if aircraft.get("status") in ("MAINTENANCE", "GROUNDED"):
        return True
    windows = aircraft.get("availability_windows", {}).get(day_name, [])
    if isinstance(windows, str):
        return windows.upper() == "MAINTENANCE"
    if isinstance(windows, list):
        return any(w.upper() == "MAINTENANCE" for w in windows)
    return False