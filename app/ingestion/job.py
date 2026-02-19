"""
Ingestion pipeline — reads bucket files, validates, upserts to DB.
Idempotent: same input = same hash = skips re-insert.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import (
    Student, Instructor, Aircraft, Simulator,
    TimeSlot, RulesDoc, IngestionRun
)
from app.ingestion.schemas import (
    StudentSchema, InstructorSchema, AircraftSchema,
    SimulatorSchema, TimeSlotSchema
)

BUCKET_DIR = Path("data/bucket")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()

def _bucket_hash() -> str:
    """Single hash of all bucket files combined."""
    combined = "".join(
        _hash_file(f) for f in sorted(BUCKET_DIR.iterdir()) if f.is_file()
    )
    return hashlib.md5(combined.encode()).hexdigest()

def _load_json(filename: str) -> list:
    return json.loads((BUCKET_DIR / filename).read_text())

def _load_text(filename: str) -> str:
    return (BUCKET_DIR / filename).read_text()


# ── Per-entity upsert functions ───────────────────────────────────────────────

def _upsert_students(db: Session) -> dict:
    raw = _load_json("students.json")
    records = [StudentSchema(**r) for r in raw]  # validates
    diff = {"upserted": [], "unchanged": []}

    for r in records:
        existing = db.get(Student, r.id)
        data = r.model_dump()

        if existing:
            changed = {k: v for k, v in data.items() if getattr(existing, k) != v}
            if changed:
                for k, v in changed.items():
                    setattr(existing, k, v)
                diff["upserted"].append(r.id)
            else:
                diff["unchanged"].append(r.id)
        else:
            db.add(Student(**data))
            diff["upserted"].append(r.id)

    return diff


def _upsert_instructors(db: Session) -> dict:
    raw = _load_json("instructors.json")
    records = [InstructorSchema(**r) for r in raw]
    diff = {"upserted": [], "unchanged": []}

    for r in records:
        existing = db.get(Instructor, r.id)
        data = r.model_dump()

        if existing:
            changed = {k: v for k, v in data.items() if getattr(existing, k) != v}
            if changed:
                for k, v in changed.items():
                    setattr(existing, k, v)
                diff["upserted"].append(r.id)
            else:
                diff["unchanged"].append(r.id)
        else:
            db.add(Instructor(**data))
            diff["upserted"].append(r.id)

    return diff


def _upsert_aircraft(db: Session) -> dict:
    raw = _load_json("aircraft.json")
    records = [AircraftSchema(**r) for r in raw]
    diff = {"upserted": [], "unchanged": []}

    for r in records:
        existing = db.get(Aircraft, r.id)
        data = r.model_dump()

        if existing:
            changed = {k: v for k, v in data.items() if getattr(existing, k) != v}
            if changed:
                for k, v in changed.items():
                    setattr(existing, k, v)
                diff["upserted"].append(r.id)
            else:
                diff["unchanged"].append(r.id)
        else:
            db.add(Aircraft(**data))
            diff["upserted"].append(r.id)

    return diff


def _upsert_simulators(db: Session) -> dict:
    raw = _load_json("simulators.json")
    records = [SimulatorSchema(**r) for r in raw]
    diff = {"upserted": [], "unchanged": []}

    for r in records:
        existing = db.get(Simulator, r.id)
        data = r.model_dump()

        if existing:
            changed = {k: v for k, v in data.items() if getattr(existing, k) != v}
            if changed:
                for k, v in changed.items():
                    setattr(existing, k, v)
                diff["upserted"].append(r.id)
            else:
                diff["unchanged"].append(r.id)
        else:
            db.add(Simulator(**data))
            diff["upserted"].append(r.id)

    return diff


def _upsert_time_slots(db: Session) -> dict:
    raw = _load_json("time_slots.json")
    records = [TimeSlotSchema(**r) for r in raw]
    diff = {"upserted": [], "unchanged": []}

    for r in records:
        existing = db.get(TimeSlot, r.id)
        data = r.model_dump()

        if not existing:
            db.add(TimeSlot(**data))
            diff["upserted"].append(r.id)
        else:
            diff["unchanged"].append(r.id)

    return diff


def _upsert_rules_docs(db: Session) -> dict:
    docs = [
        ("doc_weather", "Weather Minima", "weather_minima.md"),
        ("doc_dispatch", "Dispatch Rules",  "dispatch_rules.md"),
    ]
    diff = {"upserted": [], "unchanged": []}

    for doc_id, title, filename in docs:
        content = _load_text(filename)
        chunks = _chunk_text(content, doc_id)
        existing = db.get(RulesDoc, doc_id)

        if existing:
            if existing.content != content:
                existing.content = content
                existing.chunks = chunks
                diff["upserted"].append(doc_id)
            else:
                diff["unchanged"].append(doc_id)
        else:
            db.add(RulesDoc(id=doc_id, title=title, content=content, chunks=chunks))
            diff["upserted"].append(doc_id)

    return diff


def _chunk_text(text: str, doc_id: str, chunk_size: int = 300) -> list[dict]:
    """Split markdown into ~300 char chunks with ids for RAG."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    for i, para in enumerate(paragraphs):
        chunks.append({
            "chunk_id": f"{doc_id}#chunk{i+1}",
            "text": para
        })
    return chunks


# ── Main entry point ──────────────────────────────────────────────────────────

def run_ingestion(db: Session, force: bool = False) -> dict:
    """
    Run full ingestion. Skips if bucket hash unchanged (idempotent).
    Set force=True to re-ingest regardless.
    """
    bucket_hash = _bucket_hash()

    # Idempotency check
    if not force:
        last_run = (
            db.query(IngestionRun)
            .order_by(IngestionRun.id.desc())
            .first()
        )
        if last_run and last_run.source_hash == bucket_hash:
            return {
                "status": "skipped",
                "reason": "bucket unchanged",
                "hash": bucket_hash
            }

    # Run all upserts
    diff_summary = {}
    try:
        diff_summary["students"]   = _upsert_students(db)
        diff_summary["instructors"] = _upsert_instructors(db)
        diff_summary["aircraft"]   = _upsert_aircraft(db)
        diff_summary["simulators"] = _upsert_simulators(db)
        diff_summary["time_slots"] = _upsert_time_slots(db)
        diff_summary["rules_docs"] = _upsert_rules_docs(db)

        db.add(IngestionRun(
            source_hash=bucket_hash,
            status="success",
            diff_summary=diff_summary
        ))
        db.commit()

    except Exception as e:
        db.rollback()
        db.add(IngestionRun(
            source_hash=bucket_hash,
            status="failed",
            diff_summary={"error": str(e)}
        ))
        db.commit()
        raise

    return {"status": "success", "hash": bucket_hash, "diff": diff_summary}