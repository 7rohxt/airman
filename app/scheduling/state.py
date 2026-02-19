"""
Tracks what's already booked during roster generation.
Acts as an in-memory constraint checker before we commit to DB.
"""
from dataclasses import dataclass, field
from datetime import date
from app.scheduling.availability import duration_hours


@dataclass
class BookingState:
    booked: dict = field(default_factory=dict)
    duty_hours: dict = field(default_factory=dict)
    aircraft_sorties: dict = field(default_factory=dict)
    sim_sessions: dict = field(default_factory=dict)
    weekly_sorties: dict = field(default_factory=dict)  # student_id → count

    def _key(self, entity_id: str, d: date) -> tuple:
        return (entity_id, d)

    def is_free(self, entity_id: str, d: date, start: str, end: str) -> bool:
        for (s, e) in self.booked.get(self._key(entity_id, d), []):
            if not (end <= s or start >= e):
                return False
        return True

    def book(self, entity_id: str, d: date, start: str, end: str):
        self.booked.setdefault(self._key(entity_id, d), []).append((start, end))

    def instructor_duty_ok(self, instructor_id: str, d: date,
                           start: str, end: str, max_hours: float) -> bool:
        used = self.duty_hours.get(self._key(instructor_id, d), 0.0)
        return (used + duration_hours(start, end) + 1.0) <= max_hours

    def log_instructor_hours(self, instructor_id: str, d: date, start: str, end: str):
        key = self._key(instructor_id, d)
        self.duty_hours[key] = self.duty_hours.get(key, 0.0) + duration_hours(start, end) + 1.0

    def aircraft_sorties_ok(self, aircraft_id: str, d: date, max_sorties: int = 2) -> bool:
        return self.aircraft_sorties.get(self._key(aircraft_id, d), 0) < max_sorties

    def log_aircraft_sortie(self, aircraft_id: str, d: date):
        key = self._key(aircraft_id, d)
        self.aircraft_sorties[key] = self.aircraft_sorties.get(key, 0) + 1

    def sim_sessions_ok(self, sim_id: str, d: date, max_sessions: int) -> bool:
        return self.sim_sessions.get(self._key(sim_id, d), 0) < max_sessions

    def log_sim_session(self, sim_id: str, d: date):
        key = self._key(sim_id, d)
        self.sim_sessions[key] = self.sim_sessions.get(key, 0) + 1

    def student_weekly_ok(self, student_id: str, required: int) -> bool:
        return self.weekly_sorties.get(student_id, 0) < required

    def log_student_sortie(self, student_id: str):
        self.weekly_sorties[student_id] = self.weekly_sorties.get(student_id, 0) + 1