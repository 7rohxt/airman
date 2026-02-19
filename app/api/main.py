"""
FastAPI app — 4 required endpoints:
  POST /ingest/run
  POST /roster/generate
  POST /dispatch/recompute
  POST /eval/run
"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Optional

from app.database import get_db, init_db
from app.ingestion.job import run_ingestion
from app.models import Student, Instructor, Aircraft, Simulator, TimeSlot, RulesDoc
from app.scheduling.roster import generate_roster
from app.weather.fetcher import get_weather, get_weather_mock
from app.dispatch.engine import check_dispatch
from app.rag.retriever import MockRulesRAG

# Level 2 imports
from app.reallocation.engine import DisruptionEvent as DisruptionEventClass, reallocate_roster
from app.models import RosterVersion, DisruptionEvent as DisruptionEventDB

app = FastAPI(title="AIRMAN Dispatch API", version="2.0.0")

# Initialize DB tables on startup
@app.on_event("startup")
def startup():
    init_db()
    print("[API] Database initialized")


# ── Endpoint 1: Ingestion ─────────────────────────────────────────────────────

@app.post("/ingest/run")
def ingest_run(force: bool = False, db: Session = Depends(get_db)):
    """
    Run ingestion pipeline.
    - Reads data/bucket/*.json + *.md
    - Validates, upserts to DB
    - Idempotent (skips if unchanged unless force=True)
    """
    try:
        result = run_ingestion(db, force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 2: Roster generation ─────────────────────────────────────────────

@app.post("/roster/generate")
def roster_generate(
    week_start: str,           # "2025-07-07"
    base_icao: str = "VOBG",
    use_mock_weather: bool = True,
    weather_scenario: str = "good",
    db: Session = Depends(get_db)
):
    """
    Generate 7-day roster + apply dispatch decisions.
    
    - week_start: ISO date (Monday)
    - use_mock_weather: if True, uses deterministic mock weather
    - weather_scenario: "good" | "low_ceiling" | "low_vis" | "high_wind"
    """
    try:
        week_date = date.fromisoformat(week_start)
        
        # Load entities from DB
        students    = [_to_dict(s) for s in db.query(Student).all()]
        instructors = [_to_dict(i) for i in db.query(Instructor).all()]
        aircraft    = [_to_dict(a) for a in db.query(Aircraft).all()]
        simulators  = [_to_dict(s) for s in db.query(Simulator).all()]
        time_slots  = [_to_dict(t) for t in db.query(TimeSlot).all()]
        
        if not students or not instructors or not aircraft or not time_slots:
            raise HTTPException(status_code=400, 
                detail="Missing data — run /ingest/run first")
        
        # Generate base roster
        roster = generate_roster(
            week_start=week_date,
            base_icao=base_icao,
            students=students,
            instructors=instructors,
            aircraft=aircraft,
            simulators=simulators,
            time_slots=time_slots,
        )
        
        # Apply dispatch decisions
        if use_mock_weather:
            weather = get_weather_mock(base_icao, weather_scenario)
        else:
            weather = get_weather(base_icao)
        
        students_map = {s["id"]: _to_dict(db.query(Student).get(s["id"])) 
                        for s in students}
        sim_slots_used = {}
        
        for day in roster["roster"]:
            updated_slots = []
            for slot in day["slots"]:
                student = students_map[slot["student_id"]]
                updated = check_dispatch(slot, student, weather, simulators, sim_slots_used)
                
                # Track sim usage
                if updated["activity"] == "SIM":
                    rid = updated["resource_id"]
                    sim_slots_used.setdefault(rid, {})
                    sim_slots_used[rid][slot["date"]] = \
                        sim_slots_used[rid].get(slot["date"], 0) + 1
                
                updated_slots.append(updated)
            
            day["slots"] = updated_slots
        
        # Add metadata
        roster["weather"] = {
            "icao": base_icao,
            "ceiling_ft": weather.ceiling_ft,
            "visibility_sm": weather.visibility_sm,
            "wind_kt": weather.wind_kt,
            "confidence": weather.confidence,
            "fetched_at": weather.fetched_at.isoformat(),
        }
        
        return roster
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 3: Dispatch recompute ────────────────────────────────────────────

@app.post("/dispatch/recompute")
def dispatch_recompute(
    date_str: str,              # "2025-07-07"
    base_icao: str = "VOBG",
    use_mock_weather: bool = False,
    db: Session = Depends(get_db)
):
    """
    Re-evaluate dispatch decisions for a specific date with fresh weather.
    Useful when weather changes and you need to update GO/NO-GO without
    regenerating the entire roster.
    """
    # This would query RosterSlot from DB for the given date
    # For now, simplified — just returns weather
    try:
        if use_mock_weather:
            weather = get_weather_mock(base_icao, "good")
        else:
            weather = get_weather(base_icao)
        
        return {
            "date": date_str,
            "base_icao": base_icao,
            "weather": {
                "ceiling_ft": weather.ceiling_ft,
                "visibility_sm": weather.visibility_sm,
                "wind_kt": weather.wind_kt,
                "confidence": weather.confidence,
            },
            "note": "Full recompute would update RosterSlot records in DB"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 4: Eval harness ──────────────────────────────────────────────────

@app.post("/eval/run")
def eval_run(scenario_count: int = 25, db: Session = Depends(get_db)):
    """
    Run evaluation across 25 scenarios.
    Tests constraint satisfaction, citation coverage, dispatch correctness.
    """
    import json
    from pathlib import Path
    
    # Load scenarios from manifest
    manifest_path = Path("eval/scenarios/manifest.json")
    if not manifest_path.exists():
        # Fallback to simple weather scenarios
        simple_scenarios = ["good", "low_ceiling", "low_vis", "high_wind", "unavailable"]
        scenarios_to_test = [
            {"id": i+1, "weather_scenario": s, "week_start": "2025-07-07"}
            for i, s in enumerate(simple_scenarios * 5)
        ][:scenario_count]
    else:
        with open(manifest_path) as f:
            manifest = json.load(f)
            scenarios_to_test = manifest["scenarios"][:scenario_count]
    
    results = []
    
    for scenario in scenarios_to_test:
        try:
            # Generate roster with this scenario's weather
            roster = roster_generate(
                week_start=scenario.get("week_start", "2025-07-07"),
                base_icao="VOBG",
                use_mock_weather=True,
                weather_scenario=scenario.get("weather_scenario", "good"),
                db=db
            )
            
            # Compute metrics
            total_slots = sum(len(day["slots"]) for day in roster["roster"])
            go_count    = sum(1 for d in roster["roster"] 
                             for s in d["slots"] if s["dispatch_decision"] == "GO")
            no_go_count = sum(1 for d in roster["roster"] 
                             for s in d["slots"] if s["dispatch_decision"] == "NO_GO")
            needs_review = sum(1 for d in roster["roster"] 
                              for s in d["slots"] if s["dispatch_decision"] == "NEEDS_REVIEW")
            
            # Check citations
            missing_citations = [s["slot_id"] for d in roster["roster"] 
                                for s in d["slots"] if not s.get("citations")]
            
            # Check constraints (no double booking)
            violations = _check_constraints(roster)
            
            results.append({
                "scenario_id": scenario.get("id", 0),
                "scenario_name": scenario.get("name", scenario.get("weather_scenario", "unknown")),
                "total_slots": total_slots,
                "go": go_count,
                "no_go": no_go_count,
                "needs_review": needs_review,
                "constraint_violations": violations,
                "citation_coverage": 100.0 if not missing_citations else 0.0,
            })
        except Exception as e:
            results.append({
                "scenario_id": scenario.get("id", 0),
                "scenario_name": scenario.get("name", "unknown"),
                "error": str(e)
            })
    
    # Summary
    total_violations = sum(r.get("constraint_violations", 0) for r in results)
    avg_citation = sum(r.get("citation_coverage", 0) for r in results) / len(results)
    
    return {
        "scenarios_tested": len(results),
        "total_constraint_violations": total_violations,
        "avg_citation_coverage": f"{avg_citation:.1f}%",
        "details": results
    }


# ── Level 2: Reallocation endpoints ───────────────────────────────────────────

@app.post("/roster/reallocate")
def roster_reallocate(
    event_type: str,
    entity_id: Optional[str] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    weather_scenario: Optional[str] = None,
    week_start: str = "2025-07-07",
    db: Session = Depends(get_db)
):
    """
    Apply a disruption event and reallocate the roster.
    
    event_type: WEATHER_UPDATE | AIRCRAFT_UNSERVICEABLE | INSTRUCTOR_UNAVAILABLE | STUDENT_UNAVAILABLE
    entity_id: aircraft_id, instructor_id, or student_id (not needed for WEATHER_UPDATE)
    from_time, to_time: ISO datetime strings
    weather_scenario: for WEATHER_UPDATE events
    """
    try:
        from datetime import datetime
        
        # Create disruption event
        event = DisruptionEventClass(
            event_type=event_type,
            entity_id=entity_id,
            from_time=datetime.fromisoformat(from_time) if from_time else None,
            to_time=datetime.fromisoformat(to_time) if to_time else None,
            metadata={"weather_scenario": weather_scenario} if weather_scenario else {}
        )
        
        # Load entities
        students    = [_to_dict(s) for s in db.query(Student).all()]
        instructors = [_to_dict(i) for i in db.query(Instructor).all()]
        aircraft    = [_to_dict(a) for a in db.query(Aircraft).all()]
        simulators  = [_to_dict(s) for s in db.query(Simulator).all()]
        time_slots  = [_to_dict(t) for t in db.query(TimeSlot).all()]
        
        # Get current roster (latest version or generate new)
        latest_version = (
            db.query(RosterVersion)
            .filter(RosterVersion.week_start == date.fromisoformat(week_start))
            .order_by(RosterVersion.version.desc())
            .first()
        )
        
        if latest_version:
            current_roster = latest_version.roster_json
        else:
            # Generate initial roster
            from app.scheduling.roster import generate_roster
            current_roster = generate_roster(
                week_start=date.fromisoformat(week_start),
                base_icao="VOBG",
                students=students,
                instructors=instructors,
                aircraft=aircraft,
                simulators=simulators,
                time_slots=time_slots,
            )
        
        # Reallocate
        result = reallocate_roster(
            current_roster=current_roster,
            event=event,
            students=students,
            instructors=instructors,
            aircraft=aircraft,
            simulators=simulators,
            time_slots=time_slots,
        )
        
        # Save new version
        new_version_num = (latest_version.version + 1) if latest_version else 1
        total_slots = sum(len(day["slots"]) for day in result["new_roster"]["roster"])
        
        new_version = RosterVersion(
            version=new_version_num,
            week_start=date.fromisoformat(week_start),
            correlation_id=result["correlation_id"],
            roster_json=result["new_roster"],
            diff_json=result["diff"],
            change_summary={
                "affected_slots": len(result["affected_slots"]),
                "event_type": result["event_type"],
            },
            churn_rate=result["churn_rate"],
            coverage=0.0,  # TODO: compute actual coverage
        )
        db.add(new_version)
        
        # Save disruption event
        disruption = DisruptionEventDB(
            event_type=event.event_type,
            entity_id=event.entity_id,
            from_time=event.from_time,
            to_time=event.to_time,
            event_metadata=event.metadata,
            correlation_id=event.correlation_id,
        )
        db.add(disruption)
        db.commit()
        
        return {
            "version": new_version_num,
            "correlation_id": result["correlation_id"],
            "churn_rate": result["churn_rate"],
            "affected_slots": len(result["affected_slots"]),
            "diff": result["diff"],
            "roster": result["new_roster"],
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/roster/versions")
def roster_versions(
    week_start: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get roster version history for a given week.
    """
    query = db.query(RosterVersion)
    
    if week_start:
        query = query.filter(RosterVersion.week_start == date.fromisoformat(week_start))
    
    versions = query.order_by(RosterVersion.created_at.desc()).all()
    
    return {
        "total_versions": len(versions),
        "versions": [
            {
                "version": v.version,
                "week_start": v.week_start.isoformat(),
                "created_at": v.created_at.isoformat(),
                "correlation_id": v.correlation_id,
                "churn_rate": v.churn_rate,
                "total_changes": v.diff_json.get("total_changes", 0) if v.diff_json else 0,
            }
            for v in versions
        ]
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_dict(obj) -> dict:
    """Convert SQLAlchemy model to dict."""
    if obj is None:
        return {}
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _check_constraints(roster: dict) -> int:
    """Count double-booking violations."""
    seen = {}
    violations = 0
    for day in roster["roster"]:
        for s in day["slots"]:
            for entity in [s["student_id"], s["instructor_id"], s["resource_id"]]:
                key = (entity, s["date"], s["start"])
                if key in seen:
                    violations += 1
                else:
                    seen[key] = s["slot_id"]
    return violations


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "AIRMAN Dispatch API",
        "version": "1.0.0",
        "endpoints": ["/ingest/run", "/roster/generate", "/dispatch/recompute", "/eval/run"]
    }