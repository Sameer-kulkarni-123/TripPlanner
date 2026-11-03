"""Destination search with Google Places API (New): cities, regions, landmarks and "near X" queries.

Flow used by the place picker (one billing session per pick):
  1. POST places:autocomplete   while the traveller types   -> suggestions (no coordinates yet)
  2. GET  places/{id}           once they pick a suggestion -> coordinates, address, types
Both calls share a session token, and step 2 asks for a Pro field (displayName), so Google
bills the typing as one free "Autocomplete session" and only charges the details call.

Generic queries ("hill stations near Bengaluru", "beaches in Goa") go to POST places:searchText,
which returns real places with coordinates in one call.

Google gives no IANA time zone, so it comes from Open-Meteo (free, no key) and is cached.
Docs: https://developers.google.com/maps/documentation/places/web-service/op-overview
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE = "https://places.googleapis.com/v1"
DETAILS_FIELDS = "id,displayName,formattedAddress,location,viewport,types,primaryType,addressComponents"
SEARCH_FIELDS = ",".join(f"places.{f}" for f in DETAILS_FIELDS.split(","))
TZ_URL = "https://api.open-meteo.com/v1/forecast"

# Google place types -> how the planner treats the destination
REGION_TYPES = {"administrative_area_level_1", "administrative_area_level_2", "administrative_area_level_3",
                "colloquial_area", "country", "archipelago", "island"}
LANDMARK_TYPES = {"tourist_attraction", "natural_feature", "national_park", "park", "hiking_area", "beach",
                  "lake", "mountain_peak", "historical_landmark", "monument", "hindu_temple", "place_of_worship",
                  "museum", "amusement_park", "zoo", "aquarium", "landmark", "point_of_interest", "establishment"}
CITY_TYPES = {"locality", "sublocality", "postal_town", "neighborhood", "sublocality_level_1"}

# Queries that ask for a kind of place rather than one named place -> Text Search
_GENERIC = re.compile(
    r"\b(near|nearby|around|close to|within|best|top|places? (?:to|in)|things to do|"
    r"beach(?:es)?|hill stations?|lakes?|waterfalls?|forts?|temples?|treks?|national parks?|"
    r"wildlife|islands?|getaways?|weekend)\b", re.I)

_tz_cache: Dict[Tuple[float, float], Optional[str]] = {}


class GooglePlacesError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.GOOGLE_MAPS_API_KEY)


def is_generic_query(q: str) -> bool:
    return bool(_GENERIC.search(q or ""))


def _headers(field_mask: Optional[str] = None) -> Dict[str, str]:
    h = {"X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY, "Content-Type": "application/json"}
    if field_mask:
        h["X-Goog-FieldMask"] = field_mask
    return h


async def _call(method: str, url: str, *, json: Any = None, params: Any = None,
                field_mask: Optional[str] = None) -> Dict[str, Any]:
    if not is_configured():
        raise GooglePlacesError("GOOGLE_MAPS_API_KEY is not configured.")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.request(method, url, json=json, params=params, headers=_headers(field_mask))
    except httpx.HTTPError as e:
        raise GooglePlacesError(f"Could not reach Google Places: {e}") from e
    if resp.status_code != 200:
        msg = resp.text[:300]
        try:
            msg = resp.json().get("error", {}).get("message") or msg
        except ValueError:
            pass
        logger.warning("Google Places HTTP %s: %s", resp.status_code, msg)
        raise GooglePlacesError(f"Google Places returned HTTP {resp.status_code}: {msg}")
    return resp.json()


def kind_of(types: List[str]) -> str:
    """'region' for states/areas/islands, 'landmark' for lakes, parks, monuments..., else 'city'."""
    t = set(types or [])
    if t & REGION_TYPES and not t & CITY_TYPES:
        return "region"
    if t & CITY_TYPES:
        return "city"
    if t & LANDMARK_TYPES:
        return "landmark"
    return "city"


# ------------------------------------------------------------------ autocomplete
async def autocomplete(q: str, session: Optional[str] = None, prefer: Optional[str] = None,
                       count: int = 8) -> List[Dict[str, Any]]:
    """Suggestions while typing: [{place_id, title, subtitle, kind, types}] (no coordinates)."""
    body: Dict[str, Any] = {"input": q, "languageCode": "en"}
    if session:
        body["sessionToken"] = session
    if prefer:
        body["regionCode"] = prefer.lower()     # formats/biases results for the traveller's country
    data = await _call("POST", f"{BASE}/places:autocomplete", json=body)
    out = []
    for s in data.get("suggestions") or []:
        p = s.get("placePrediction")
        if not p or not p.get("placeId"):
            continue
        fmt = p.get("structuredFormat") or {}
        types = p.get("types") or []
        out.append({
            "place_id": p["placeId"],
            "title": (fmt.get("mainText") or {}).get("text") or (p.get("text") or {}).get("text", ""),
            "subtitle": (fmt.get("secondaryText") or {}).get("text"),
            "kind": kind_of(types),
            "types": types,
        })
    return out[:count]


# ------------------------------------------------------------------ details / text search
async def details(place_id: str, session: Optional[str] = None) -> Dict[str, Any]:
    params = {"languageCode": "en"}
    if session:
        params["sessionToken"] = session
    return await _call("GET", f"{BASE}/places/{place_id}", params=params, field_mask=DETAILS_FIELDS)


async def text_search(q: str, prefer: Optional[str] = None, count: int = 8) -> List[Dict[str, Any]]:
    body: Dict[str, Any] = {"textQuery": q, "languageCode": "en", "pageSize": min(max(count, 1), 20)}
    if prefer:
        body["regionCode"] = prefer.lower()
    data = await _call("POST", f"{BASE}/places:searchText", json=body, field_mask=SEARCH_FIELDS)
    return data.get("places") or []


def components(place: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """country, country_code, admin1 and locality from addressComponents."""
    out: Dict[str, Optional[str]] = {"country": None, "country_code": None, "admin1": None, "locality": None}
    for c in place.get("addressComponents") or []:
        types = c.get("types") or []
        if "country" in types:
            out["country"], out["country_code"] = c.get("longText"), (c.get("shortText") or "").upper()
        elif "administrative_area_level_1" in types:
            out["admin1"] = c.get("longText")
        elif "locality" in types and not out["locality"]:
            out["locality"] = c.get("longText")
    return out


async def timezone_for(lat: float, lon: float) -> Optional[str]:
    """IANA time zone for a point (Open-Meteo, no key). Cached to ~1 km."""
    key = (round(lat, 2), round(lon, 2))
    if key in _tz_cache:
        return _tz_cache[key]
    tz = None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(TZ_URL, params={"latitude": lat, "longitude": lon, "timezone": "auto",
                                                    "current": "temperature_2m", "forecast_days": 1})
        if resp.status_code == 200:
            tz = resp.json().get("timezone")
    except (httpx.HTTPError, ValueError) as e:
        logger.info("Time zone lookup failed for %s: %s", key, e)
    if tz and tz != "GMT":
        _tz_cache[key] = tz
    return tz
