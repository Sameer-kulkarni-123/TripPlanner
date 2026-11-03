"""Place search for any city, state, region or landmark: coordinates, time zone and the airport to fly into.

- With GOOGLE_MAPS_API_KEY set, Google Places (app/integrations/google_places.py) does the searching:
  type-ahead suggestions, regions like Ladakh, landmarks like Pangong Lake and generic queries like
  "hill stations near Bengaluru". Everything below is the free fallback used without a key.

- Places come from the Open-Meteo geocoding API (GeoNames data, no key needed for
  non-commercial use): https://open-meteo.com/en/docs/geocoding-api
  Cities, towns *and* states/regions are kept, so "Goa" finds the Indian state instead of
  a small town of the same name elsewhere.
- Results are ranked: exact name first, then population, with places in the traveller's own
  country (``prefer``) weighted up.
- Airports come from Nuitee / LiteAPI static data (GET /data/iataCodes), cached in memory.
  The airport is picked by distance, but international airports get a head start and
  military / closed-to-airline fields are pushed back, so Hyderabad gets HYD, not Begumpet.
- When the geocoder finds nothing (nicknames like "Coorg"), Gemini may suggest candidates,
  and each one is kept only if the geocoder confirms a real place near it.
"""
import asyncio
import difflib
import logging
import math
import re
import unicodedata
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
# GeoNames feature codes: populated places, and areas a traveller might name as a destination
_POPULATED = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLG", "PPLL", "PPLS", "PPLX"}
_REGIONS = {"ADM1", "ADM2", "ISL", "ISLS", "RGN", "AREA", "PEN", "CST"}
MAX_AIRPORT_KM = 250
REGION_POPULATION_FLOOR = 300_000   # GeoNames often has no population for states; rank them like a mid-size city
PREFERRED_COUNTRY_WEIGHT = 5

# Airports that are near a city centre but don't take regular airline traffic.
SECONDARY_AIRPORTS = {"BPM"}  # Hyderabad Begumpet (business/VIP since HYD opened)
_MILITARY = re.compile(r"\b(air ?force|air base|afb|naval|army|heliport|military|airfield|afs)\b", re.I)

# Destinations whose map centre is a poor base for a trip; use the usual tourist base instead.
# (normalised name, country) -> (lat, lon, base name)
REGION_HUBS = {
    ("goa", "IN"): (15.4989, 73.8278, "Panaji"),
    ("kodagu", "IN"): (12.4244, 75.7382, "Madikeri"),
    ("coorg", "IN"): (12.4244, 75.7382, "Madikeri"),
    ("ladakh", "IN"): (34.1526, 77.5771, "Leh"),
    ("andaman and nicobar islands", "IN"): (11.6234, 92.7265, "Sri Vijaya Puram (Port Blair)"),
    ("sikkim", "IN"): (27.3389, 88.6065, "Gangtok"),
    ("kerala", "IN"): (9.9312, 76.2673, "Kochi"),
    ("bali", "ID"): (-8.5069, 115.2625, "Ubud"),
    ("jammu and kashmir", "IN"): (34.0837, 74.7973, "Srinagar"),
    ("kashmir", "IN"): (34.0837, 74.7973, "Srinagar"),
    ("himachal pradesh", "IN"): (32.2432, 77.1892, "Manali"),
    ("spiti", "IN"): (32.2276, 78.0710, "Kaza"),
    ("spiti valley", "IN"): (32.2276, 78.0710, "Kaza"),
    ("uttarakhand", "IN"): (30.0869, 78.2676, "Rishikesh"),
    ("rajasthan", "IN"): (26.9124, 75.7873, "Jaipur"),
    ("meghalaya", "IN"): (25.5788, 91.8933, "Shillong"),
    ("lakshadweep", "IN"): (10.5667, 72.6417, "Kavaratti"),
    ("andaman islands", "IN"): (11.6234, 92.7265, "Sri Vijaya Puram (Port Blair)"),
    ("nilgiris", "IN"): (11.4102, 76.6950, "Ooty"),
    ("the nilgiris", "IN"): (11.4102, 76.6950, "Ooty"),
}

_airports: Optional[List[Dict[str, Any]]] = None
_airports_lock = asyncio.Lock()


class PlacesError(Exception):
    pass


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


async def _load_airports() -> List[Dict[str, Any]]:
    """IATA airport list from LiteAPI, normalised to {code, name, lat, lon, country}. Cached."""
    global _airports
    if _airports is not None:
        return _airports
    async with _airports_lock:
        if _airports is not None:
            return _airports
        if not settings.NUITEE_API_KEY:
            return []
        url = f"{settings.NUITEE_API_BASE_URL.rstrip('/')}/data/iataCodes"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"accept": "application/json", "X-API-Key": settings.NUITEE_API_KEY})
            if resp.status_code != 200:
                logger.warning("LiteAPI /data/iataCodes HTTP %s", resp.status_code)
                return []
            rows = resp.json().get("data") or []
        except Exception as e:  # network or JSON problems: airports are optional
            logger.warning("Could not load airport list: %s", e)
            return []
        out = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            code = r.get("code") or r.get("iata") or r.get("iataCode")
            lat = _num(r.get("latitude", r.get("lat")))
            lon = _num(r.get("longitude", r.get("lon", r.get("lng"))))
            if not code or lat is None or lon is None:
                continue
            out.append({
                "code": str(code).upper(),
                "name": r.get("name") or r.get("airportName") or str(code),
                "lat": lat,
                "lon": lon,
                "country": (r.get("countryCode") or r.get("country_code") or r.get("country") or "").upper(),
            })
        _airports = out
        return out


def _airport_score(distance_km: float, a: Dict[str, Any]) -> float:
    """Lower is better: distance, minus a head start for international airports, plus a penalty
    for fields airlines don't use."""
    score = distance_km
    name = str(a.get("name") or "").lower()
    if "international" in name or "intl" in name:
        score -= 45
    if a["code"] in SECONDARY_AIRPORTS or _MILITARY.search(name):
        score += 150
    return score


def nearest_airport(lat: float, lon: float, country: str, airports: List[Dict[str, Any]],
                    prefer_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Airport to fly into: the hinted code if it is real and in range, otherwise the best-scored one."""
    same = [a for a in airports if not country or a["country"] == country.upper()] or airports
    in_range = [(d, a) for a in same if (d := _km(lat, lon, a["lat"], a["lon"])) <= MAX_AIRPORT_KM]
    if not in_range:
        return None
    hit = None
    if prefer_code:
        hit = next(((d, a) for d, a in in_range if a["code"] == str(prefer_code).upper()), None)
    d, a = hit or min(in_range, key=lambda x: _airport_score(*x))
    return {"code": a["code"], "name": a["name"], "distance_km": round(d, 1)}


def _kind(feature_code: Optional[str]) -> str:
    return "region" if feature_code in _REGIONS else "city"


def _rank(results: List[Dict[str, Any]], query: str, prefer: Optional[str]) -> List[Dict[str, Any]]:
    q = _norm(query.split(",")[0])
    pref = (prefer or "").upper()

    def key(item):
        i, r = item
        n = _norm(r.get("name"))
        exact = n == q
        # Exact name first; whole-word / near matches next; loose fuzzy hits (a different place that
        # merely resembles the query, e.g. "Ladakh" -> the Odisha village "Ladakhaman") go last.
        close = exact or q in n.split() or difflib.SequenceMatcher(None, n, q).ratio() >= 0.85
        pop = r.get("population") or 0
        if _kind(r.get("feature_code")) == "region":
            pop = max(pop, REGION_POPULATION_FLOOR)
        if pref and (r.get("country_code") or "").upper() == pref:
            pop *= PREFERRED_COUNTRY_WEIGHT
        return (0 if exact else 1 if close else 2, -pop, i)

    return [r for _, r in sorted(enumerate(results), key=key)]


def _dedupe(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop a district/region when a place of the same name in the same country is already listed nearby."""
    out: List[Dict[str, Any]] = []
    for r in results:
        dup = any(
            _norm(o.get("name")) == _norm(r.get("name")) and o.get("country_code") == r.get("country_code")
            and _km(o["latitude"], o["longitude"], r["latitude"], r["longitude"]) < 80
            for o in out
        )
        if not dup:
            out.append(r)
    return out


def _to_place(r: Dict[str, Any], airports: List[Dict[str, Any]], *, airport_hint: Optional[str] = None,
              source: str = "Open-Meteo geocoding (GeoNames)") -> Dict[str, Any]:
    cc = (r.get("country_code") or "").upper()
    lat, lon = r["latitude"], r["longitude"]
    kind = _kind(r.get("feature_code"))
    base = None
    hub = REGION_HUBS.get((_norm(r.get("name")), cc))
    if hub:
        lat, lon, base = hub
        kind = "region"
    return {
        "city": r.get("name"),
        "region": r.get("admin1") if r.get("admin1") and r.get("admin1") != r.get("name") else None,
        "country": r.get("country"),
        "country_code": cc,
        "latitude": lat,
        "longitude": lon,
        "timezone": r.get("timezone"),
        "population": r.get("population"),
        "kind": kind,
        "base": base,
        "airport": nearest_airport(lat, lon, cc, airports, airport_hint) if airports else None,
        "source": source,
    }


async def _geocode(query: str, count: int, country_code: Optional[str]) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"name": query, "count": max(1, min(count * 3, 40)), "language": "en", "format": "json"}
    if country_code:
        params["countryCode"] = country_code.upper()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(GEOCODE_URL, params=params)
    except httpx.HTTPError as e:
        raise PlacesError(f"Could not reach the geocoding service: {e}") from e
    if resp.status_code != 200:
        raise PlacesError(f"Geocoding service returned HTTP {resp.status_code}.")
    out = []
    for r in resp.json().get("results") or []:
        lat, lon = _num(r.get("latitude")), _num(r.get("longitude"))
        if lat is None or lon is None:
            continue
        out.append({**r, "latitude": lat, "longitude": lon})
    return out


def _useful(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in rows if r.get("feature_code") in _POPULATED or r.get("feature_code") in _REGIONS] or rows


def _hub_keys(query: str) -> List[tuple]:
    """REGION_HUBS entries whose name equals the query, or starts with it (3+ letters) while typing."""
    q = _norm(query.split(",")[0])
    if len(q) < 3:
        return []
    return [k for k in REGION_HUBS if k[0] == q or k[0].startswith(q)]


async def _hub_places(query: str, airports: List[Dict[str, Any]], country_code: Optional[str]) -> List[Dict[str, Any]]:
    """Known regions the geocoder lacks (e.g. Ladakh): build them from the base town's geocoder record."""
    out: List[Dict[str, Any]] = []
    for name, cc in _hub_keys(query):
        if country_code and country_code.upper() != cc:
            continue
        lat, lon, base = REGION_HUBS[(name, cc)]
        base_name = base.split("(")[-1].rstrip(")") if "(" in base else base
        try:
            hits = await _geocode(base_name, 5, cc)
        except PlacesError:
            continue
        if not hits:
            continue
        near = min(hits, key=lambda h: _km(lat, lon, h["latitude"], h["longitude"]))
        rec = {**near, "name": name.title(), "admin1": None}   # keep tz/country, label it as the region
        place = _to_place(rec, airports, source="Known region, base town confirmed with Open-Meteo geocoding")
        out.append(place)
    return out


async def search_places(query: str, count: int = 8, country_code: Optional[str] = None,
                        prefer: Optional[str] = None, use_ai: bool = True) -> List[Dict[str, Any]]:
    """Places matching a name. ``country_code`` filters; ``prefer`` only ranks that country higher."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    from app.integrations import google_places as gpl
    if gpl.is_configured() and not country_code:
        try:
            hits = await google_search_places(q, count=count, prefer=prefer)
            if hits:
                return hits
        except gpl.GooglePlacesError as e:
            logger.warning("Google Places search failed, falling back to Open-Meteo: %s", e)
    raw = await _geocode(q, count, country_code)
    if not raw and "," in q:
        raw = await _geocode(q.split(",")[0].strip(), count, country_code)
    ranked = _dedupe(_rank(_useful(raw), q, prefer))
    airports = await _load_airports()
    places = [_to_place(r, airports) for r in ranked[:count]]
    hubs = await _hub_places(q, airports, country_code)
    if hubs:   # curated regions lead; drop geocoder rows that are the same place
        places = hubs + [p for p in places if not any(p["city"] == h["city"] and p["country_code"] == h["country_code"] for h in hubs)]
        places = places[:count]
    if not places and use_ai:
        places = await resolve_with_gemini(q, prefer=prefer or country_code, airports=airports)
    return places


# ------------------------------------------------------------------ Gemini, checked against the geocoder
def _resolver_prompt(query: str, prefer: Optional[str]) -> str:
    home = f" The traveller lives in country code {prefer}; prefer places there when the name is ambiguous." if prefer else ""
    return f"""A traveller typed this as a trip destination: "{query}".{home}
Name up to 3 real places they most likely mean (city, town, state, island or region), most likely first.
Use the official name a map would use (e.g. "Kodagu" for "Coorg"). For a region, give the coordinates of
the town travellers usually stay in.
Return JSON: {{"candidates": [{{"name": str, "kind": "city" or "region", "country_code": 2-letter ISO code,
"latitude": number, "longitude": number, "airport_iata": 3-letter code of the airport most travellers use, or null}}]}}"""


async def resolve_with_gemini(query: str, *, prefer: Optional[str] = None,
                              airports: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Ask Gemini what the traveller meant, then keep only candidates the geocoder confirms nearby."""
    from app.integrations import llm  # local import: place search works without a language model

    if not llm.is_configured():
        return []
    try:
        raw = await llm.generate_json(_resolver_prompt(query, prefer), temperature=0.0, timeout=30)
    except llm.LLMError as e:
        logger.info("Gemini place resolver unavailable: %s", e)
        return []
    cands = raw.get("candidates") if isinstance(raw, dict) else None
    if not isinstance(cands, list):
        return []
    if airports is None:
        airports = await _load_airports()

    out: List[Dict[str, Any]] = []
    for c in cands[:3]:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        lat, lon = _num(c.get("latitude")), _num(c.get("longitude"))
        cc = str(c.get("country_code") or "").upper()[:2] or None
        try:
            hits = _useful(await _geocode(str(c["name"]), 5, cc))
        except PlacesError:
            continue
        if not hits:
            continue  # the geocoder doesn't know it: never invent a place
        is_region = c.get("kind") == "region"
        if lat is not None and lon is not None:
            near = min(hits, key=lambda h: _km(lat, lon, h["latitude"], h["longitude"]))
            if _km(lat, lon, near["latitude"], near["longitude"]) > (150 if is_region else 60):
                continue  # Gemini's coordinates don't match the real place
        else:
            near = hits[0]
        place = _to_place(near, airports, airport_hint=c.get("airport_iata"),
                          source="Gemini suggestion, confirmed with Open-Meteo geocoding")
        if is_region:
            place["kind"] = "region"
            if lat is not None and lon is not None and not place.get("base"):
                place["latitude"], place["longitude"] = lat, lon   # Gemini's base town, checked to be nearby
                if airports:
                    place["airport"] = nearest_airport(lat, lon, place["country_code"], airports, c.get("airport_iata"))
        if not any(p["city"] == place["city"] and p["country_code"] == place["country_code"] for p in out):
            out.append(place)
    return out


# ------------------------------------------------------------------ Google Places (when configured)
async def _from_google(gp: Dict[str, Any], airports: List[Dict[str, Any]],
                       source: str = "Google Places") -> Optional[Dict[str, Any]]:
    """A Google place -> the same shape as the Open-Meteo results above."""
    from app.integrations import google_places as gpl

    loc = gp.get("location") or {}
    lat, lon = _num(loc.get("latitude")), _num(loc.get("longitude"))
    if lat is None or lon is None:
        return None
    name = (gp.get("displayName") or {}).get("text") or gp.get("formattedAddress") or ""
    comps = gpl.components(gp)
    cc = comps["country_code"] or ""
    kind = gpl.kind_of(gp.get("types") or [])
    base = None
    hub = REGION_HUBS.get((_norm(name), cc))
    if hub:
        lat, lon, base = hub
        kind = "region"
    # Landmarks are shown with their town ("Pangong Lake, Ladakh"); cities with their state
    region = comps["admin1"] if kind != "landmark" else (comps["locality"] or comps["admin1"])
    if region == name:
        region = None
    return {
        "city": name,
        "region": region,
        "country": comps["country"],
        "country_code": cc,
        "latitude": lat,
        "longitude": lon,
        "timezone": await gpl.timezone_for(lat, lon),
        "population": None,
        "kind": kind,
        "base": base,
        "address": gp.get("formattedAddress"),
        "place_id": gp.get("id"),
        "airport": nearest_airport(lat, lon, cc, airports) if airports else None,
        "source": source,
    }


async def google_search_places(query: str, count: int = 8, prefer: Optional[str] = None) -> List[Dict[str, Any]]:
    """Full places (with coordinates) for a free-text query, via Google Text Search."""
    from app.integrations import google_places as gpl

    rows = await gpl.text_search(query, prefer=prefer, count=count)
    airports = await _load_airports()
    out: List[Dict[str, Any]] = []
    for gp in rows:
        p = await _from_google(gp, airports, source="Google Places text search")
        if p and not any(o["city"] == p["city"] and o["country_code"] == p["country_code"] for o in out):
            out.append(p)
    return out[:count]


async def suggest_places(query: str, session: Optional[str] = None, prefer: Optional[str] = None,
                         count: int = 8) -> Dict[str, Any]:
    """For the type-ahead picker.
    With Google: {"suggestions": [...no coordinates, resolve with place_details...], "results": [...]}
    where "results" holds ready places for generic queries ("beaches near Goa").
    Without Google: {"suggestions": [], "results": <Open-Meteo search>}."""
    from app.integrations import google_places as gpl

    if not gpl.is_configured():
        return {"provider": "open-meteo", "suggestions": [], "results": await search_places(query, count, prefer=prefer)}
    try:
        suggestions = await gpl.autocomplete(query, session=session, prefer=prefer, count=count)
        results = await google_search_places(query, count=6, prefer=prefer) if gpl.is_generic_query(query) else []
    except gpl.GooglePlacesError as e:
        logger.warning("Google Places unavailable, using Open-Meteo: %s", e)
        return {"provider": "open-meteo", "suggestions": [], "results": await search_places(query, count, prefer=prefer)}
    # Don't list a place twice when text search already resolved it
    have = {r.get("place_id") for r in results}
    return {"provider": "google", "suggestions": [s for s in suggestions if s["place_id"] not in have], "results": results}


async def place_details(place_id: str, session: Optional[str] = None) -> Dict[str, Any]:
    from app.integrations import google_places as gpl

    try:
        gp = await gpl.details(place_id, session=session)
    except gpl.GooglePlacesError as e:
        raise PlacesError(str(e)) from e
    place = await _from_google(gp, await _load_airports())
    if not place:
        raise PlacesError("Google Places returned no coordinates for that place.")
    return place
