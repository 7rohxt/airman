"""
Weather integration — fetches METAR data for an ICAO airfield.
Uses aviationweather.gov API (free, no key needed).

Flow:
  get_weather(icao) → checks in-memory cache → fetches if stale → parses METAR
  If fetch fails → returns fallback with confidence="unknown"
"""
import urllib.request
import urllib.error
import json
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional


CACHE_TTL_MINUTES = 30


@dataclass
class WeatherReport:
    icao: str
    ceiling_ft: Optional[int]       # None = clear / unlimited
    visibility_sm: Optional[float]
    wind_kt: Optional[int]
    crosswind_kt: Optional[int]
    raw_metar: str
    fetched_at: datetime
    confidence: str                  # "live" | "cached" | "unknown"

    def is_stale(self) -> bool:
        return datetime.utcnow() - self.fetched_at > timedelta(minutes=CACHE_TTL_MINUTES)


# ── In-memory cache ───────────────────────────────────────────────────────────

_cache: dict[str, WeatherReport] = {}


def get_weather(icao: str,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None) -> WeatherReport:
    """
    Main entry point. Returns WeatherReport for the given ICAO.
    start_time/end_time are accepted for API compatibility but
    METAR is always current conditions.
    """
    icao = icao.upper()

    # Return cached if still fresh
    if icao in _cache and not _cache[icao].is_stale():
        report = _cache[icao]
        report.confidence = "cached"
        return report

    # Try to fetch live
    try:
        raw = _fetch_metar(icao)
        report = _parse_metar(icao, raw)
        _cache[icao] = report
        return report
    except Exception as e:
        print(f"[weather] fetch failed for {icao}: {e}")
        return _fallback(icao)


# ── Fetcher ───────────────────────────────────────────────────────────────────

def _fetch_metar(icao: str, timeout: int = 5) -> str:
    """Fetch raw METAR string from aviationweather.gov."""
    url = (
        f"https://aviationweather.gov/api/data/metar"
        f"?ids={icao}&format=json&taf=false"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "airman-dispatch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())

    if not data:
        raise ValueError(f"No METAR data returned for {icao}")

    return data[0].get("rawOb", "") or data[0].get("metar", "")


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_metar(icao: str, raw: str) -> WeatherReport:
    """
    Parse key fields from a raw METAR string.
    We only need ceiling, visibility, wind for dispatch decisions.
    """
    ceiling_ft    = _parse_ceiling(raw)
    visibility_sm = _parse_visibility(raw)
    wind_kt, crosswind_kt = _parse_wind(raw)

    return WeatherReport(
        icao=icao,
        ceiling_ft=ceiling_ft,
        visibility_sm=visibility_sm,
        wind_kt=wind_kt,
        crosswind_kt=crosswind_kt,
        raw_metar=raw,
        fetched_at=datetime.utcnow(),
        confidence="live",
    )


def _parse_ceiling(raw: str) -> Optional[int]:
    """
    Find lowest BKN or OVC layer → ceiling in feet.
    Returns None if sky clear (SKC/CLR/CAVOK).
    """
    if any(x in raw for x in ("SKC", "CLR", "CAVOK", "NSC")):
        return None  # unlimited

    pattern = r'(BKN|OVC)(\d{3})'
    matches = re.findall(pattern, raw)
    if not matches:
        return None

    # lowest layer (each unit = 100 ft)
    return min(int(h) * 100 for _, h in matches)


def _parse_visibility(raw: str) -> Optional[float]:
    """
    Parse visibility in statute miles.
    Handles: '9999' (meters), '10SM', '6SM', '1/2SM' formats.
    """
    # SM format (US)
    sm_match = re.search(r'(\d+(?:/\d+)?|\d+\s+\d+/\d+)SM', raw)
    if sm_match:
        vis_str = sm_match.group(1).strip()
        if "/" in vis_str:
            parts = vis_str.split()
            if len(parts) == 2:
                whole = float(parts[0])
                num, den = parts[1].split("/")
                return whole + float(num) / float(den)
            num, den = vis_str.split("/")
            return float(num) / float(den)
        return float(vis_str)

    # Metric format (9999 = >10km ≈ 6SM, otherwise convert)
    m_match = re.search(r'\b(\d{4})\b', raw)
    if m_match:
        meters = int(m_match.group(1))
        if meters == 9999:
            return 10.0
        return round(meters / 1609.34, 1)

    return None


def _parse_wind(raw: str) -> tuple[Optional[int], Optional[int]]:
    """
    Returns (wind_kt, crosswind_kt).
    Crosswind is estimated as ~30% of total wind (simplified).
    """
    match = re.search(r'\d{3}(\d{2,3})(?:G\d{2,3})?KT', raw)
    if match:
        wind = int(match.group(1))
        crosswind = int(wind * 0.3)  # simplified estimate
        return wind, crosswind

    # Variable wind
    if re.search(r'VRB\d{2}KT', raw):
        spd = int(re.search(r'VRB(\d{2})KT', raw).group(1))
        return spd, spd  # treat all as crosswind (worst case)

    return None, None


# ── Fallback ──────────────────────────────────────────────────────────────────

def _fallback(icao: str) -> WeatherReport:
    """Used when fetch fails — dispatcher should mark slot NEEDS_REVIEW."""
    return WeatherReport(
        icao=icao,
        ceiling_ft=None,
        visibility_sm=None,
        wind_kt=None,
        crosswind_kt=None,
        raw_metar="UNAVAILABLE",
        fetched_at=datetime.utcnow(),
        confidence="unknown",
    )


# ── Mock for testing (no internet needed) ────────────────────────────────────

def get_weather_mock(icao: str, scenario: str = "good") -> WeatherReport:
    """
    Returns deterministic weather for testing.
    scenario: "good" | "low_ceiling" | "low_vis" | "high_wind" | "unavailable"
    """
    scenarios = {
        "good":        WeatherReport(icao, 5000, 10.0, 8,  2,  "VOBG 010800Z 27008KT 9999 FEW050 25/14 Q1013", datetime.utcnow(), "live"),
        "low_ceiling": WeatherReport(icao, 800,  8.0,  6,  2,  "VOBG 010800Z 27006KT 8000 OVC008 18/16 Q1008", datetime.utcnow(), "live"),
        "low_vis":     WeatherReport(icao, 3000, 2.0,  5,  1,  "VOBG 010800Z 27005KT 3200 BKN030 20/18 Q1010", datetime.utcnow(), "live"),
        "high_wind":   WeatherReport(icao, 4000, 8.0,  25, 10, "VOBG 010800Z 27025KT 9999 FEW040 22/12 Q1015", datetime.utcnow(), "live"),
        "unavailable": _fallback(icao),
    }
    return scenarios.get(scenario, scenarios["good"])