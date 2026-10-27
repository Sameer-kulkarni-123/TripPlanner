"""Straight-line distance helpers. These are NOT travel times; results must be labelled accordingly."""
from math import asin, cos, radians, sin, sqrt
from typing import List, Optional

from app.agents.hotel.schemas import GeoPoint

EARTH_RADIUS_KM = 6371.0088
DISTANCE_SOURCE = "haversine straight-line distance (not travel time)"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearest_reference_km(
    latitude: Optional[float], longitude: Optional[float], points: List[GeoPoint]
) -> Optional[float]:
    """Distance to the closest reference point, or None if hotel coordinates/reference points are missing."""
    if latitude is None or longitude is None or not points:
        return None
    return round(min(haversine_km(latitude, longitude, p.latitude, p.longitude) for p in points), 3)


def mean_reference_km(
    latitude: Optional[float], longitude: Optional[float], points: List[GeoPoint]
) -> Optional[float]:
    """Average distance to all reference points (better proxy for 'central to the itinerary')."""
    if latitude is None or longitude is None or not points:
        return None
    dists = [haversine_km(latitude, longitude, p.latitude, p.longitude) for p in points]
    return round(sum(dists) / len(dists), 3)
