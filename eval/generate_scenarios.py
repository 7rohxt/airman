"""
Generate 25 eval scenarios with different combinations of:
- Weather conditions (good, low_ceiling, low_vis, high_wind, unavailable)
- Week start dates
- Student availability variations
- Aircraft maintenance schedules
"""
import json
from pathlib import Path
from datetime import date, timedelta
from copy import deepcopy

EVAL_DIR = Path("eval/scenarios")
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# Base bucket data
BASE_BUCKET = Path("data/bucket")

WEATHER_SCENARIOS = ["good", "low_ceiling", "low_vis", "high_wind", "unavailable"]


def generate_scenarios():
    """Generate 25 unique scenario files."""
    scenarios = []
    
    # Scenario 1-5: Different weather conditions, same bucket
    week_start = date(2025, 7, 7)
    for i, weather in enumerate(WEATHER_SCENARIOS, 1):
        scenarios.append({
            "id": i,
            "name": f"baseline_weather_{weather}",
            "description": f"Standard roster with {weather} weather",
            "week_start": week_start.isoformat(),
            "weather_scenario": weather,
            "bucket_variant": "baseline",
        })
    
    # Scenario 6-10: Good weather, different week starts
    for i in range(5):
        week = week_start + timedelta(weeks=i)
        scenarios.append({
            "id": 6 + i,
            "name": f"week_shift_{i+1}",
            "description": f"Week starting {week.isoformat()}",
            "week_start": week.isoformat(),
            "weather_scenario": "good",
            "bucket_variant": "baseline",
        })
    
    # Scenario 11-15: Low ceiling weather, student availability reduced
    for i in range(5):
        scenarios.append({
            "id": 11 + i,
            "name": f"reduced_availability_{i+1}",
            "description": f"Students with {60-i*10}% availability, low ceiling",
            "week_start": week_start.isoformat(),
            "weather_scenario": "low_ceiling",
            "bucket_variant": f"reduced_avail_{i+1}",
        })
    
    # Scenario 16-20: High priority student variations
    for i in range(5):
        scenarios.append({
            "id": 16 + i,
            "name": f"priority_mix_{i+1}",
            "description": f"Priority distribution variant {i+1}",
            "week_start": week_start.isoformat(),
            "weather_scenario": "good",
            "bucket_variant": f"priority_{i+1}",
        })
    
    # Scenario 21-25: Aircraft maintenance windows
    for i in range(5):
        scenarios.append({
            "id": 21 + i,
            "name": f"maintenance_window_{i+1}",
            "description": f"Aircraft AC0{i+1 if i < 2 else 1} in maintenance",
            "week_start": week_start.isoformat(),
            "weather_scenario": "low_vis",
            "bucket_variant": f"maintenance_{i+1}",
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
        "scenarios": scenarios
    }
    with open(EVAL_DIR / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✅ Generated {len(scenarios)} scenarios in {EVAL_DIR}")
    return scenarios


if __name__ == "__main__":
    generate_scenarios()