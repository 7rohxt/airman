"""
Test roster generation end-to-end using mock bucket data.
No DB needed — runs purely in memory.

  python app/scheduling/test_roster.py
"""
import sys, json
sys.path.insert(0, ".")

from datetime import date
from app.scheduling.roster import generate_roster

# Load mock data
def load(f): return json.load(open(f"data/bucket/{f}"))

students   = load("students.json")
instructors = load("instructors.json")
aircraft   = load("aircraft.json")
simulators = load("simulators.json")
time_slots = load("time_slots.json")

roster = generate_roster(
    week_start=date(2025, 7, 7),   # a Monday
    base_icao="VOBG",
    students=students,
    instructors=instructors,
    aircraft=aircraft,
    simulators=simulators,
    time_slots=time_slots,
)

# ── Print summary ─────────────────────────────────────────────────────────────
total_slots = sum(len(day["slots"]) for day in roster["roster"])
flight_slots = sum(
    1 for day in roster["roster"]
    for s in day["slots"] if s["activity"] == "FLIGHT"
)
sim_slots = sum(
    1 for day in roster["roster"]
    for s in day["slots"] if s["activity"] == "SIM"
)

print(f"\n📅 Week: {roster['week_start']}  |  Base: {roster['base_icao']}")
print(f"✅ Total assigned slots : {total_slots}")
print(f"✈️  Flight slots         : {flight_slots}")
print(f"🖥️  SIM slots            : {sim_slots}")
print(f"⚠️  Unassigned           : {len(roster['unassigned'])}")

print("\n── Sample slots ──")
for day in roster["roster"]:
    if day["slots"]:
        for s in day["slots"][:2]:
            print(f"  {day['date']} | {s['slot_id']} | {s['activity']:6} | "
                  f"{s['sortie_type']:15} | {s['student_id']} + {s['instructor_id']} "
                  f"+ {s['resource_id']} | {s['dispatch_decision']}")

# ── Constraint checks ─────────────────────────────────────────────────────────
print("\n── Constraint validation ──")
seen = {}  # (entity_id, date, start) → slot_id
violations = 0

for day in roster["roster"]:
    for s in day["slots"]:
        for entity in [s["student_id"], s["instructor_id"], s["resource_id"]]:
            key = (entity, s["date"], s["start"])
            if key in seen:
                print(f"  ❌ DOUBLE BOOKING: {entity} at {s['date']} {s['start']}"
                      f" in {s['slot_id']} AND {seen[key]}")
                violations += 1
            else:
                seen[key] = s["slot_id"]

if violations == 0:
    print("  ✅ Zero hard constraint violations")
else:
    print(f"  ❌ {violations} violations found!")

# ── Citation check ────────────────────────────────────────────────────────────
missing_citations = [
    s["slot_id"] for day in roster["roster"]
    for s in day["slots"] if not s.get("citations")
]
if missing_citations:
    print(f"  ❌ Missing citations: {missing_citations}")
else:
    print("  ✅ All slots have citations")