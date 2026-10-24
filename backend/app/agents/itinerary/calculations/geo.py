"""Deterministic geographic helpers (no LLM arithmetic — TDD 5.7 / 7.5)."""
import math
from typing import Optional, Tuple

WALK_SPEED_KMH = 4.5
WALK_MAX_KM = 1.2
TRANSIT_SPEED_KMH = 18.0          # average door-to-door urban transit/taxi speed
TRANSIT_OVERHEAD_MIN = 10         # waiting / getting to the stop
UNKNOWN_TRAVEL_MIN = 30           # used when either end has no coordinates
ROUTE_FACTOR = 1.3                # straight-line -> street distance


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def _round_up(minutes: float, step: int = 5) -> int:
    return int(math.ceil(minutes / step) * step)


def estimate_travel(
    a: Optional[Tuple[float, float]], b: Optional[Tuple[float, float]]
) -> Tuple[Optional[float], int, str]:
    """Return (distance_km, minutes, mode). mode in {'none','walk','transit','unknown'}."""
    if a is None or b is None:
        return None, UNKNOWN_TRAVEL_MIN, "unknown"
    km = haversine_km(a, b) * ROUTE_FACTOR
    if km < 0.05:
        return round(km, 2), 0, "none"
    if km <= WALK_MAX_KM:
        return round(km, 2), max(5, _round_up(km / WALK_SPEED_KMH * 60)), "walk"
    return round(km, 2), _round_up(TRANSIT_OVERHEAD_MIN + km / TRANSIT_SPEED_KMH * 60), "transit"


def centroid(points):
    pts = [p for p in points if p is not None]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
