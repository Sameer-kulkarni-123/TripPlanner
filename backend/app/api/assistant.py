"""Turn a free-text trip request into a structured draft (the orchestrator's 'extract requirements' step).

Gemini only extracts what the traveller wrote; places are then resolved with the geocoder,
dates and numbers are checked in code, and anything missing is listed so the UI can ask for it.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.itinerary.calculations.filtering import INTEREST_KEYWORDS
from app.integrations import gemini
from app.integrations.places import PlacesError, _load_airports, nearest_airport, search_places

router = APIRouter()

PACES = ("relaxed", "moderate", "packed")
CURRENCIES = ("INR", "USD", "EUR", "GBP")


class DraftRequest(BaseModel):
    text: str = Field(min_length=3, max_length=1000, description="e.g. '3 days in Mysuru from Bengaluru next month, 2 adults'")
    today: Optional[date] = Field(default=None, description="The traveller's local date, used for 'next weekend' etc.")
    home_city: Optional[str] = Field(default=None, description="Used as the origin when the text doesn't name one")


def _prompt(text: str, today: date) -> str:
    interests = ", ".join(INTEREST_KEYWORDS.keys())
    return f"""Today is {today.isoformat()} ({today.strftime('%A')}). Extract the trip the traveller describes.
Only use what the text says or clearly implies. Use null for anything not stated.

Traveller wrote: \"\"\"{text}\"\"\"

Return JSON with exactly these keys:
- "destination": city, town, state or region as commonly written, or null
- "destination_country_code": 2-letter ISO country code of the place they most likely mean, or null
- "destination_airport_iata": 3-letter code of the airport most travellers use for it, or null
- "origin": city they start from, or null
- "origin_country_code": 2-letter ISO country code of the origin, or null
- "start_date": "YYYY-MM-DD" or null (resolve relative dates like "next Friday" from today)
- "end_date": "YYYY-MM-DD" or null
- "nights": integer or null
- "adults": integer or null
- "children_ages": list of integers (empty if none)
- "interests": list chosen only from [{interests}]
- "avoid": list chosen only from the same values
- "pace": one of "relaxed", "moderate", "packed", or null
- "activity_budget": number or null (money for activities only, if stated)
- "currency": one of "INR", "USD", "EUR", "GBP", or null
- "wheelchair": true if they mention wheelchair or step-free access, otherwise false"""


async def _place(name: Optional[str], *, country: Optional[str] = None, prefer: Optional[str] = None,
                 airport: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Resolve a name with the geocoder. Gemini's country/airport guesses only steer the choice:
    a place is used only if the geocoder knows it, and an airport only if it is real and nearby."""
    if not name:
        return None
    cc = country.upper()[:2] if isinstance(country, str) and len(country) >= 2 else None
    try:
        hits = await search_places(name, count=5, prefer=cc or prefer)
    except PlacesError:
        hits = []
    if not hits and "," in name:
        try:
            hits = await search_places(name.split(",")[0], count=5, prefer=cc or prefer)
        except PlacesError:
            hits = []
    if not hits:
        return None
    best = next((h for h in hits if cc and h.get("country_code") == cc), hits[0])
    if isinstance(airport, str) and len(airport) == 3 and (best.get("airport") or {}).get("code") != airport.upper():
        airports = await _load_airports()
        picked = nearest_airport(best["latitude"], best["longitude"], best.get("country_code") or "", airports, airport)
        if picked and picked["code"] == airport.upper():
            best = {**best, "airport": picked}
    return best


@router.post("/trip-draft")
async def trip_draft(req: DraftRequest):
    today = req.today or date.today()
    try:
        raw = await gemini.generate_json(_prompt(req.text, today), temperature=0.0)
    except gemini.GeminiError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not isinstance(raw, dict):
        raise HTTPException(status_code=502, detail="Gemini returned an unexpected format.")

    notes: List[str] = []

    def as_date(v: Any) -> Optional[date]:
        try:
            return date.fromisoformat(str(v)[:10]) if v else None
        except ValueError:
            return None

    start, end = as_date(raw.get("start_date")), as_date(raw.get("end_date"))
    nights = raw.get("nights") if isinstance(raw.get("nights"), int) and 0 < raw.get("nights") <= 30 else None
    if start and not end and nights:
        end = start + timedelta(days=nights)
    if start and end and end <= start:
        notes.append("The return date was not after the start date, so it was ignored.")
        end = None
    if start and start < today:
        notes.append("The start date was in the past, so it was ignored.")
        start = end = None

    adults = raw.get("adults") if isinstance(raw.get("adults"), int) and 1 <= raw.get("adults") <= 9 else None
    kids = [a for a in (raw.get("children_ages") or []) if isinstance(a, int) and 0 <= a <= 17][:6]
    allowed = set(INTEREST_KEYWORDS)
    interests = [i for i in (raw.get("interests") or []) if i in allowed]
    avoid = [i for i in (raw.get("avoid") or []) if i in allowed and i not in interests]
    pace = raw.get("pace") if raw.get("pace") in PACES else None
    currency = raw.get("currency") if raw.get("currency") in CURRENCIES else None
    budget = raw.get("activity_budget")
    budget = float(budget) if isinstance(budget, (int, float)) and budget > 0 else None

    origin_name = raw.get("origin") or req.home_city
    origin = await _place(origin_name, country=raw.get("origin_country_code"))
    destination = await _place(raw.get("destination"), country=raw.get("destination_country_code"),
                               prefer=(origin or {}).get("country_code"), airport=raw.get("destination_airport_iata"))
    if raw.get("destination") and not destination:
        notes.append(f"Couldn't find '{raw.get('destination')}' on the map; pick the destination yourself.")
    if origin_name and not origin:
        notes.append(f"Couldn't find '{origin_name}' on the map; pick where you're starting from.")

    missing = [k for k, v in (("destination", destination), ("dates", start and end)) if not v]
    return {
        "destination": destination,
        "origin": origin,
        "start_date": start,
        "end_date": end,
        "adults": adults,
        "children_ages": kids,
        "interests": interests,
        "avoid": avoid,
        "pace": pace,
        "activity_budget": budget,
        "currency": currency,
        "wheelchair": bool(raw.get("wheelchair")),
        "missing": missing,
        "notes": notes,
        "source": "Gemini extraction, places from Open-Meteo geocoding",
    }
