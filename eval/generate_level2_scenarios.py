"""
Generate 30 Level 2 disruption test scenarios.

Scenarios cover:
- Weather changes (good → bad, bad → good)
- Aircraft unserviceable
- Instructor unavailable
- Student unavailable
- Multiple simultaneous disruptions
"""
import json
from pathlib import Path
from datetime import date, timedelta

EVAL_DIR = Path("eval/level2_scenarios")
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def generate_level2_scenarios():
    """Generate 30 disruption scenarios."""
    scenarios = []
    
    base_date = date(2025, 7, 7)
    
    # Scenarios 1-5: Weather deteriorates mid-week
    for i in range(5):
        day_offset = i + 2  # Day 2-6 of the week
        scenarios.append({
            "id": i + 1,
            "name": f"weather_deteriorate_day_{day_offset}",
            "description": f"Good weather → low ceiling on day {day_offset}",
            "week_start": base_date.isoformat(),
            "initial_weather": "good",
            "disruption": {
                "event_type": "WEATHER_UPDATE",
                "weather_scenario": "low_ceiling",
                "from_time": (base_date + timedelta(days=day_offset)).isoformat(),
                "to_time": (base_date + timedelta(days=day_offset)).isoformat(),
            }
        })
    
    # Scenarios 6-10: Weather improves mid-week
    for i in range(5):
        day_offset = i + 2
        scenarios.append({
            "id": i + 6,
            "name": f"weather_improve_day_{day_offset}",
            "description": f"Low ceiling → good weather on day {day_offset}",
            "week_start": (base_date + timedelta(weeks=1)).isoformat(),
            "initial_weather": "low_ceiling",
            "disruption": {
                "event_type": "WEATHER_UPDATE",
                "weather_scenario": "good",
                "from_time": (base_date + timedelta(weeks=1, days=day_offset)).isoformat(),
                "to_time": (base_date + timedelta(weeks=1, days=day_offset)).isoformat(),
            }
        })
    
    # Scenarios 11-15: Aircraft unserviceable for varying durations
    durations = [1, 2, 3, 1, 2]  # days
    aircraft_ids = ["AC01", "AC02", "AC01", "AC02", "AC01"]
    for i, (duration, ac_id) in enumerate(zip(durations, aircraft_ids)):
        scenarios.append({
            "id": i + 11,
            "name": f"aircraft_{ac_id}_down_{duration}d",
            "description": f"{ac_id} unserviceable for {duration} day(s)",
            "week_start": (base_date + timedelta(weeks=2)).isoformat(),
            "initial_weather": "good",
            "disruption": {
                "event_type": "AIRCRAFT_UNSERVICEABLE",
                "entity_id": ac_id,
                "from_time": (base_date + timedelta(weeks=2, days=1)).isoformat() + "T00:00:00",
                "to_time": (base_date + timedelta(weeks=2, days=1 + duration)).isoformat() + "T23:59:59",
            }
        })
    
    # Scenarios 16-20: Instructor unavailable
    instructor_ids = ["I001", "I002", "I001", "I002", "I001"]
    for i, inst_id in enumerate(instructor_ids):
        day_offset = (i % 3) + 1
        scenarios.append({
            "id": i + 16,
            "name": f"instructor_{inst_id}_sick_day_{day_offset}",
            "description": f"{inst_id} unavailable on day {day_offset}",
            "week_start": (base_date + timedelta(weeks=3)).isoformat(),
            "initial_weather": "good",
            "disruption": {
                "event_type": "INSTRUCTOR_UNAVAILABLE",
                "entity_id": inst_id,
                "from_time": (base_date + timedelta(weeks=3, days=day_offset)).isoformat() + "T00:00:00",
                "to_time": (base_date + timedelta(weeks=3, days=day_offset)).isoformat() + "T23:59:59",
            }
        })
    
    # Scenarios 21-25: Student unavailable
    student_ids = ["S001", "S002", "S003", "S001", "S002"]
    for i, stu_id in enumerate(student_ids):
        day_offset = (i % 4) + 1
        scenarios.append({
            "id": i + 21,
            "name": f"student_{stu_id}_absent_day_{day_offset}",
            "description": f"{stu_id} unavailable on day {day_offset}",
            "week_start": (base_date + timedelta(weeks=4)).isoformat(),
            "initial_weather": "good",
            "disruption": {
                "event_type": "STUDENT_UNAVAILABLE",
                "entity_id": stu_id,
                "from_time": (base_date + timedelta(weeks=4, days=day_offset)).isoformat() + "T00:00:00",
                "to_time": (base_date + timedelta(weeks=4, days=day_offset)).isoformat() + "T23:59:59",
            }
        })
    
    # Scenarios 26-30: Multiple simultaneous disruptions
    multi_disruptions = [
        {
            "name": "weather_and_aircraft",
            "desc": "Bad weather + AC01 down",
            "events": [
                {"event_type": "WEATHER_UPDATE", "weather_scenario": "high_wind"},
                {"event_type": "AIRCRAFT_UNSERVICEABLE", "entity_id": "AC01",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"}
            ]
        },
        {
            "name": "instructor_and_student",
            "desc": "I001 sick + S001 absent",
            "events": [
                {"event_type": "INSTRUCTOR_UNAVAILABLE", "entity_id": "I001",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"},
                {"event_type": "STUDENT_UNAVAILABLE", "entity_id": "S001",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"}
            ]
        },
        {
            "name": "aircraft_and_instructor",
            "desc": "AC02 down + I002 sick",
            "events": [
                {"event_type": "AIRCRAFT_UNSERVICEABLE", "entity_id": "AC02",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"},
                {"event_type": "INSTRUCTOR_UNAVAILABLE", "entity_id": "I002",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"}
            ]
        },
        {
            "name": "triple_disruption",
            "desc": "Weather + AC01 down + I001 sick",
            "events": [
                {"event_type": "WEATHER_UPDATE", "weather_scenario": "low_vis"},
                {"event_type": "AIRCRAFT_UNSERVICEABLE", "entity_id": "AC01",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"},
                {"event_type": "INSTRUCTOR_UNAVAILABLE", "entity_id": "I001",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"}
            ]
        },
        {
            "name": "all_aircraft_down",
            "desc": "Both aircraft unserviceable",
            "events": [
                {"event_type": "AIRCRAFT_UNSERVICEABLE", "entity_id": "AC01",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"},
                {"event_type": "AIRCRAFT_UNSERVICEABLE", "entity_id": "AC02",
                 "from_time": "T00:00:00", "to_time": "T23:59:59"}
            ]
        }
    ]
    
    for i, multi in enumerate(multi_disruptions):
        scenarios.append({
            "id": i + 26,
            "name": multi["name"],
            "description": multi["desc"],
            "week_start": (base_date + timedelta(weeks=5 + i)).isoformat(),
            "initial_weather": "good",
            "disruption": {
                "event_type": "MULTIPLE",
                "events": multi["events"]
            }
        })
    
    # Write scenario files
    for scenario in scenarios:
        filepath = EVAL_DIR / f"scenario_{scenario['id']:02d}.json"
        with open(filepath, 'w') as f:
            json.dump(scenario, f, indent=2)
    
    # Write manifest
    manifest = {
        "total_scenarios": len(scenarios),
        "generated_at": date.today().isoformat(),
        "description": "Level 2 disruption test scenarios",
        "scenarios": scenarios
    }
    with open(EVAL_DIR / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✅ Generated {len(scenarios)} Level 2 disruption scenarios in {EVAL_DIR}")
    return scenarios


if __name__ == "__main__":
    generate_level2_scenarios()