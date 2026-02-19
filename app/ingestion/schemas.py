from pydantic import BaseModel, field_validator
from typing import Optional
from enum import Enum


class MaintenanceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MAINTENANCE = "MAINTENANCE"
    GROUNDED = "GROUNDED"


class StudentSchema(BaseModel):
    id: str
    name: str
    stage: str
    priority: int = 5
    solo_eligible: bool = False
    required_sorties_per_week: int = 3
    availability: dict[str, list[str]]


class InstructorSchema(BaseModel):
    id: str
    name: str
    ratings: list[str]
    currency: dict[str, str]        # sortie_type -> ISO date string
    max_duty_hours_per_day: float = 8.0
    sim_instructor: bool = False
    availability: dict[str, list[str]]


class AircraftSchema(BaseModel):
    id: str
    type: str
    status: MaintenanceStatus = MaintenanceStatus.AVAILABLE
    availability_windows: dict[str, list[str]]
    sim_mapping: Optional[str] = None


class SimulatorSchema(BaseModel):
    id: str
    type: str
    max_sessions_per_day: int = 4
    availability: dict[str, list[str]]


class TimeSlotSchema(BaseModel):
    id: str
    start_time: str
    end_time: str
    label: Optional[str] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def valid_time_format(cls, v):
        h, m = v.split(":")
        assert 0 <= int(h) <= 23 and 0 <= int(m) <= 59, f"Bad time: {v}"
        return v