"""
Utility functions for time/availability checks.
"""
from datetime import datetime, date, timedelta


def parse_time(t: str) -> datetime:
    """'08:00' → datetime object (date doesn't matter, just time comparison)"""
    return datetime.strptime(t, "%H:%M")


def slot_fits_in_window(slot_start: str, slot_end: str, window: str) -> bool:
    """
    Check if a slot (e.g. '08:00'-'10:00') fits inside an availability window
    like '07:00-17:00'. Returns False for 'MAINTENANCE' or missing windows.
    """
    if not window or window.upper() == "MAINTENANCE":
        return False
    try:
        w_start, w_end = window.split("-")
        return parse_time(w_start) <= parse_time(slot_start) and \
               parse_time(slot_end) <= parse_time(w_end)
    except Exception:
        return False


def is_available(entity_availability: dict, day_name: str,
                 slot_start: str, slot_end: str) -> bool:
    """
    Check if a student/instructor/aircraft is available on a given day+slot.
    entity_availability: {"Mon": ["08:00-12:00", "14:00-17:00"], ...}
    """
    windows = entity_availability.get(day_name, [])
    if isinstance(windows, str):
        windows = [windows]
    return any(slot_fits_in_window(slot_start, slot_end, w) for w in windows)


def get_day_name(d: date) -> str:
    """date → 'Mon', 'Tue', etc."""
    return d.strftime("%a")


def duration_hours(start: str, end: str) -> float:
    """'08:00', '10:00' → 2.0"""
    return (parse_time(end) - parse_time(start)).seconds / 3600


def week_dates(week_start: date) -> list[date]:
    """Return Mon–Fri dates for a given week start (must be Monday)."""
    return [week_start + timedelta(days=i) for i in range(5)]  # Mon-Fri only