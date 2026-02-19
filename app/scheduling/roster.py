"""
Roster generator — builds a 7-day draft schedule.

Strategy (greedy, priority-ordered):
  For each day → each slot → each student (sorted by priority):
    1. Skip if student already hit weekly sortie cap
    2. Find a valid instructor (rated, available, duty hours ok)
    3. Find a valid aircraft (available, not in maintenance, sorties ok)
    4. Book all three → FLIGHT slot
    5. If no aircraft → SIM fallback
    6. If nothing works → unassigned
"""
from datetime import date
from typing import Optional

from app.scheduling.availability import is_available, get_day_name, week_dates
from app.scheduling.state import BookingState
from app.scheduling.sortie_rules import (
    pick_sortie_type, instructor_can_teach, is_maintenance
)


def generate_roster(
    week_start: date,
    base_icao: str,
    students: list[dict],
    instructors: list[dict],
    aircraft: list[dict],
    simulators: list[dict],
    time_slots: list[dict],
) -> dict:
    state = BookingState()
    roster_days = []
    unassigned = []

    sorted_students = sorted(students, key=lambda s: s["priority"])

    for day in week_dates(week_start):
        day_name = get_day_name(day)
        day_slots = []

        for slot in time_slots:
            slot_start = slot["start_time"]
            slot_end   = slot["end_time"]
            slot_id    = f"{day.strftime('D%d')}-{slot['id']}"

            for student in sorted_students:
                # ── Weekly cap check ──────────────────────────────────────
                if not state.student_weekly_ok(student["id"],
                                               student["required_sorties_per_week"]):
                    continue

                if not is_available(student["availability"], day_name, slot_start, slot_end):
                    continue

                if not state.is_free(student["id"], day, slot_start, slot_end):
                    continue

                sortie_type = pick_sortie_type(student)

                # ── Try FLIGHT ────────────────────────────────────────────
                instructor = _find_instructor(
                    instructors, sortie_type,
                    day_name, slot_start, slot_end, day, state
                )
                ac = _find_aircraft(
                    aircraft, day_name, slot_start, slot_end, day, state
                ) if instructor else None

                if instructor and ac:
                    state.book(student["id"],    day, slot_start, slot_end)
                    state.book(instructor["id"], day, slot_start, slot_end)
                    state.book(ac["id"],         day, slot_start, slot_end)
                    state.log_instructor_hours(instructor["id"], day, slot_start, slot_end)
                    state.log_aircraft_sortie(ac["id"], day)
                    state.log_student_sortie(student["id"])

                    day_slots.append(_make_slot(
                        slot_id, slot_start, slot_end,
                        activity="FLIGHT", sortie_type=sortie_type,
                        student_id=student["id"], instructor_id=instructor["id"],
                        resource_id=ac["id"], dispatch_decision="GO",
                        reasons=["INSTRUCTOR_CURRENCY_OK", "AIRCRAFT_AVAILABLE"],
                        citations=["rules:doc_dispatch#chunk2", "rules:doc_dispatch#chunk3"],
                        date=day,
                    ))
                    break

                # ── SIM fallback ──────────────────────────────────────────
                sim_inst = _find_sim_instructor(
                    instructors, day_name, slot_start, slot_end, day, state
                )
                sim = _find_simulator(
                    simulators, day_name, slot_start, slot_end, day, state
                ) if sim_inst else None

                if sim_inst and sim:
                    state.book(student["id"],  day, slot_start, slot_end)
                    state.book(sim_inst["id"], day, slot_start, slot_end)
                    state.book(sim["id"],      day, slot_start, slot_end)
                    state.log_instructor_hours(sim_inst["id"], day, slot_start, slot_end)
                    state.log_sim_session(sim["id"], day)
                    state.log_student_sortie(student["id"])

                    day_slots.append(_make_slot(
                        slot_id, slot_start, slot_end,
                        activity="SIM", sortie_type="SIM_PROCEDURES",
                        student_id=student["id"], instructor_id=sim_inst["id"],
                        resource_id=sim["id"], dispatch_decision="GO",
                        reasons=["NO_AIRCRAFT_AVAILABLE", "SIM_FALLBACK"],
                        citations=["rules:doc_dispatch#chunk4"],
                        date=day,
                    ))
                    break

        roster_days.append({"date": day.isoformat(), "slots": day_slots})

    # Students with zero assignments this week
    assigned_ids = {s["student_id"] for day in roster_days for s in day["slots"]}
    for student in students:
        if student["id"] not in assigned_ids:
            unassigned.append({
                "entity": "student",
                "id": student["id"],
                "reason": "No available slot matched constraints"
            })

    return {
        "week_start": week_start.isoformat(),
        "base_icao": base_icao,
        "roster": roster_days,
        "unassigned": unassigned
    }


# ── Finders ───────────────────────────────────────────────────────────────────

def _find_instructor(instructors, sortie_type, day_name,
                     slot_start, slot_end, day, state) -> Optional[dict]:
    for inst in instructors:
        if not instructor_can_teach(inst, sortie_type):
            continue
        if not is_available(inst["availability"], day_name, slot_start, slot_end):
            continue
        if not state.is_free(inst["id"], day, slot_start, slot_end):
            continue
        if not state.instructor_duty_ok(inst["id"], day, slot_start, slot_end,
                                         inst["max_duty_hours_per_day"]):
            continue
        return inst
    return None


def _find_sim_instructor(instructors, day_name, slot_start,
                          slot_end, day, state) -> Optional[dict]:
    for inst in instructors:
        if not inst.get("sim_instructor"):
            continue
        if not is_available(inst["availability"], day_name, slot_start, slot_end):
            continue
        if not state.is_free(inst["id"], day, slot_start, slot_end):
            continue
        if not state.instructor_duty_ok(inst["id"], day, slot_start, slot_end,
                                         inst["max_duty_hours_per_day"]):
            continue
        return inst
    return None


def _find_aircraft(aircraft, day_name, slot_start,
                   slot_end, day, state) -> Optional[dict]:
    for ac in aircraft:
        if is_maintenance(ac, day_name):
            continue
        if not is_available(ac["availability_windows"], day_name, slot_start, slot_end):
            continue
        if not state.is_free(ac["id"], day, slot_start, slot_end):
            continue
        if not state.aircraft_sorties_ok(ac["id"], day):
            continue
        return ac
    return None


def _find_simulator(simulators, day_name, slot_start,
                    slot_end, day, state) -> Optional[dict]:
    for sim in simulators:
        if not is_available(sim["availability"], day_name, slot_start, slot_end):
            continue
        if not state.is_free(sim["id"], day, slot_start, slot_end):
            continue
        if not state.sim_sessions_ok(sim["id"], day, sim["max_sessions_per_day"]):
            continue
        return sim
    return None


# ── Slot builder ──────────────────────────────────────────────────────────────

def _make_slot(slot_id, start, end, activity, sortie_type,
               student_id, instructor_id, resource_id,
               dispatch_decision, reasons, citations, date) -> dict:
    return {
        "slot_id": slot_id, "date": date.isoformat(),
        "start": start, "end": end,
        "activity": activity, "sortie_type": sortie_type,
        "student_id": student_id, "instructor_id": instructor_id,
        "resource_id": resource_id, "dispatch_decision": dispatch_decision,
        "reasons": reasons, "citations": citations,
    }