"""
Dispatch decision engine.

Takes a roster slot + weather report → updates dispatch_decision.
Rules come from weather_minima.md (hardcoded here, later via RAG).

Decision flow:
  weather unavailable         → NEEDS_REVIEW
  SIM activity                → GO always (weather irrelevant)
  ceiling/vis/wind below mins → NO_GO → try convert to SIM
  all ok                      → GO
"""
from app.weather.fetcher import WeatherReport
from typing import Optional


# ── Minima table (mirrors weather_minima.md) ──────────────────────────────────
# stage_prefix → {ceiling_ft, visibility_sm, wind_kt, crosswind_kt}

STAGE_MINIMA = {
    "PPL-1": {"ceiling_ft": 2500, "visibility_sm": 8.0, "wind_kt": 10, "crosswind_kt": 8},
    "PPL-2": {"ceiling_ft": 2500, "visibility_sm": 8.0, "wind_kt": 10, "crosswind_kt": 8},
    "PPL-3": {"ceiling_ft": 1500, "visibility_sm": 5.0, "wind_kt": 15, "crosswind_kt": 12},
    "PPL-4": {"ceiling_ft": 1500, "visibility_sm": 5.0, "wind_kt": 15, "crosswind_kt": 12},
}

SOLO_MINIMA = {"ceiling_ft": 3000, "visibility_sm": 10.0, "wind_kt": 10, "crosswind_kt": 8}

# Citation refs for each rule chunk
CITATIONS = {
    "ceiling":    "rules:doc_weather#chunk4",
    "visibility": "rules:doc_weather#chunk5",
    "wind":       "rules:doc_weather#chunk6",
    "solo":       "rules:doc_weather#chunk7",
    "sim_ok":     "rules:doc_weather#chunk8",
    "unavailable":"rules:doc_weather#chunk9",
}


def check_dispatch(
    slot: dict,
    student: dict,
    weather: WeatherReport,
    simulators: list[dict],
    sim_slots_used: dict,       # sim_id → {date → count} for capacity check
) -> dict:
    """
    Evaluates a roster slot against weather and returns updated slot dict.
    Does NOT mutate input — returns a new dict.
    """
    slot = dict(slot)  # shallow copy

    # SIM activity → always GO, skip weather check
    if slot["activity"] == "SIM":
        slot["dispatch_decision"] = "GO"
        slot["reasons"] = ["SIM_NO_WEATHER_REQUIRED"]
        slot["citations"] = [CITATIONS["sim_ok"]]
        return slot

    # Weather unavailable → NEEDS_REVIEW
    if weather.confidence == "unknown":
        slot["dispatch_decision"] = "NEEDS_REVIEW"
        slot["reasons"] = ["WEATHER_UNAVAILABLE"]
        slot["citations"] = [CITATIONS["unavailable"]]
        return slot

    # Get applicable minima
    is_solo = slot["sortie_type"] == "SOLO"
    minima = SOLO_MINIMA if is_solo else _get_stage_minima(student["stage"])

    # Check each condition
    violations = _check_violations(weather, minima, is_solo)

    if not violations:
        slot["dispatch_decision"] = "GO"
        slot["reasons"] = ["WX_ABOVE_MINIMA"]
        slot["citations"] = [CITATIONS["ceiling"], CITATIONS["visibility"]]
        return slot

    # NO_GO — try SIM conversion
    sim = _find_available_sim(slot, simulators, sim_slots_used)
    if sim:
        slot["activity"] = "SIM"
        slot["sortie_type"] = "SIM_PROCEDURES"
        slot["resource_id"] = sim["id"]
        slot["dispatch_decision"] = "NO_GO"
        slot["reasons"] = violations + ["CONVERTED_TO_SIM"]
        slot["citations"] = [CITATIONS["ceiling"], CITATIONS["visibility"], CITATIONS["sim_ok"]]
        return slot

    # NO_GO, no sim available
    slot["dispatch_decision"] = "NO_GO"
    slot["reasons"] = violations + ["NO_SIM_AVAILABLE"]
    slot["citations"] = [CITATIONS["ceiling"], CITATIONS["visibility"]]
    return slot


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_stage_minima(stage: str) -> dict:
    """Match stage string to minima. Default to strictest if unknown."""
    for key in STAGE_MINIMA:
        if stage.startswith(key):
            return STAGE_MINIMA[key]
    return STAGE_MINIMA["PPL-1"]


def _check_violations(weather: WeatherReport, minima: dict, is_solo: bool) -> list[str]:
    violations = []

    if weather.ceiling_ft is not None and weather.ceiling_ft < minima["ceiling_ft"]:
        violations.append("WX_BELOW_CEILING_MINIMA")

    if weather.visibility_sm is not None and weather.visibility_sm < minima["visibility_sm"]:
        violations.append("WX_BELOW_VIS_MINIMA")

    if weather.wind_kt is not None and weather.wind_kt > minima["wind_kt"]:
        violations.append("WX_WIND_EXCEEDED")

    if weather.crosswind_kt is not None and weather.crosswind_kt > minima["crosswind_kt"]:
        violations.append("WX_CROSSWIND_EXCEEDED")

    return violations


def _find_available_sim(slot: dict, simulators: list[dict],
                         sim_slots_used: dict) -> Optional[dict]:
    """Find a sim that has capacity on this slot's date."""
    date_str = slot["date"]
    for sim in simulators:
        used = sim_slots_used.get(sim["id"], {}).get(date_str, 0)
        if used < sim["max_sessions_per_day"]:
            return sim
    return None