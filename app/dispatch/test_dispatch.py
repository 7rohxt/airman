"""
Test weather + dispatch integration.
Uses mock weather so no internet needed.

  python app/dispatch/test_dispatch.py
"""
import sys, json
sys.path.insert(0, ".")

from datetime import date
from app.scheduling.roster import generate_roster
from app.weather.fetcher import get_weather_mock
from app.dispatch.engine import check_dispatch

def load(f): return json.load(open(f"data/bucket/{f}"))

students    = load("students.json")
instructors = load("instructors.json")
aircraft    = load("aircraft.json")
simulators  = load("simulators.json")
time_slots  = load("time_slots.json")

students_map = {s["id"]: s for s in students}

# Generate base roster
roster = generate_roster(
    week_start=date(2025, 7, 7),
    base_icao="VOBG",
    students=students,
    instructors=instructors,
    aircraft=aircraft,
    simulators=simulators,
    time_slots=time_slots,
)

print("\n── Testing 4 weather scenarios ──\n")

scenarios = ["good", "low_ceiling", "low_vis", "high_wind"]

for scenario in scenarios:
    weather = get_weather_mock("VOBG", scenario)
    sim_slots_used = {}

    updated_slots = []
    for day in roster["roster"]:
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

    # Summary
    go         = sum(1 for s in updated_slots if s["dispatch_decision"] == "GO")
    no_go      = sum(1 for s in updated_slots if s["dispatch_decision"] == "NO_GO")
    needs_rev  = sum(1 for s in updated_slots if s["dispatch_decision"] == "NEEDS_REVIEW")
    converted  = sum(1 for s in updated_slots 
                     if "CONVERTED_TO_SIM" in s.get("reasons", []))

    print(f"Scenario: {scenario:<12} | "
          f"GO={go}  NO_GO={no_go}  NEEDS_REVIEW={needs_rev}  "
          f"SIM_conversions={converted}")

    # Show first NO_GO detail
    for s in updated_slots:
        if s["dispatch_decision"] == "NO_GO":
            print(f"  ↳ {s['slot_id']} | {s['sortie_type']} | "
                  f"reasons={s['reasons']}")
            print(f"     citations={s['citations']}")
            break

print("\n── Citation coverage ──")
missing = [s["slot_id"] for s in updated_slots if not s.get("citations")]
if missing:
    print(f"  ❌ Missing citations: {missing}")
else:
    print("  ✅ All slots have citations")