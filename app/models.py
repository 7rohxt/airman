from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    Date, Time, JSON, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


# ── Enums ────────────────────────────────────────────────────────────────────

class ActivityType(str, enum.Enum):
    FLIGHT = "FLIGHT"
    SIM = "SIM"

class DispatchDecision(str, enum.Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class SortieType(str, enum.Enum):
    CIRCUITS = "CIRCUITS"
    NAV = "NAV"
    SOLO = "SOLO"
    CHK_PREP = "CHK_PREP"
    SIM_PROCEDURES = "SIM_PROCEDURES"

class MaintenanceStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    MAINTENANCE = "MAINTENANCE"
    GROUNDED = "GROUNDED"


# ── Core entities ─────────────────────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True)              # e.g. "S123"
    name = Column(String, nullable=False)
    stage = Column(String, nullable=False)             # e.g. "PPL-3"
    priority = Column(Integer, default=5)              # 1=highest
    solo_eligible = Column(Boolean, default=False)
    required_sorties_per_week = Column(Integer, default=3)
    availability = Column(JSON, nullable=False)        # {"Mon": ["09:00-12:00"], ...}
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Instructor(Base):
    __tablename__ = "instructors"

    id = Column(String, primary_key=True)              # e.g. "I045"
    name = Column(String, nullable=False)
    ratings = Column(JSON, nullable=False)             # ["CIRCUITS", "NAV", "CHK_PREP"]
    currency = Column(JSON, nullable=False)            # {"NAV": "2024-12-01", ...}
    max_duty_hours_per_day = Column(Float, default=8.0)
    sim_instructor = Column(Boolean, default=False)
    availability = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Aircraft(Base):
    __tablename__ = "aircraft"

    id = Column(String, primary_key=True)              # e.g. "AC02"
    type = Column(String, nullable=False)              # e.g. "C172"
    status = Column(SAEnum(MaintenanceStatus), default=MaintenanceStatus.AVAILABLE)
    availability_windows = Column(JSON, nullable=False)
    sim_mapping = Column(String, nullable=True)        # maps to simulator id
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Simulator(Base):
    __tablename__ = "simulators"

    id = Column(String, primary_key=True)              # e.g. "SIM01"
    type = Column(String, nullable=False)              # e.g. "C172-SIM"
    max_sessions_per_day = Column(Integer, default=4)
    availability = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(String, primary_key=True)              # e.g. "SLOT_AM1"
    start_time = Column(String, nullable=False)        # "08:00"
    end_time = Column(String, nullable=False)          # "10:00"
    label = Column(String)                             # "Morning Block 1"


class RulesDoc(Base):
    __tablename__ = "rules_docs"

    id = Column(String, primary_key=True)              # e.g. "doc_weather"
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    chunks = Column(JSON, nullable=True)               # pre-chunked for RAG
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Roster + Dispatch ─────────────────────────────────────────────────────────

class RosterSlot(Base):
    __tablename__ = "roster_slots"

    id = Column(String, primary_key=True)              # e.g. "D1-S1"
    week_start = Column(Date, nullable=False)
    date = Column(Date, nullable=False)
    base_icao = Column(String, nullable=False)

    slot_id = Column(String, ForeignKey("time_slots.id"), nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)

    activity = Column(SAEnum(ActivityType), nullable=False)
    sortie_type = Column(SAEnum(SortieType), nullable=False)

    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    instructor_id = Column(String, ForeignKey("instructors.id"), nullable=False)
    resource_id = Column(String, nullable=False)       # aircraft or sim id

    dispatch_decision = Column(SAEnum(DispatchDecision), nullable=False)
    reasons = Column(JSON, default=list)               # ["WX_BELOW_MINIMA", ...]
    citations = Column(JSON, default=list)             # ["rules:doc_weather#chunk3"]

    created_at = Column(DateTime, server_default=func.now())


class UnassignedEntry(Base):
    __tablename__ = "unassigned"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_start = Column(Date, nullable=False)
    entity = Column(String, nullable=False)            # "student" | "instructor"
    entity_id = Column(String, nullable=False)
    reason = Column(String, nullable=False)


# ── Ingestion tracking ────────────────────────────────────────────────────────

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime, server_default=func.now())
    source_hash = Column(String, nullable=False)       # hash of input files
    status = Column(String, default="success")
    diff_summary = Column(JSON, default=dict)          # what changed


# ── Weather cache ─────────────────────────────────────────────────────────────

class WeatherCache(Base):
    __tablename__ = "weather_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    icao = Column(String, nullable=False)
    fetched_at = Column(DateTime, server_default=func.now())
    valid_until = Column(DateTime, nullable=False)
    ceiling_ft = Column(Integer, nullable=True)
    visibility_sm = Column(Float, nullable=True)
    wind_kt = Column(Integer, nullable=True)
    raw = Column(JSON, nullable=True)
    confidence = Column(String, default="live")        # "live" | "cached" | "unknown"