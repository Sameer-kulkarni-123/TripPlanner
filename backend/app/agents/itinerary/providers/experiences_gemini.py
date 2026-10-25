"""Activity suggestions from Google Gemini, used when live Nuitee experiences are unavailable.

The model only proposes candidates. Application code then:
- validates every field and drops malformed items,
- drops places whose coordinates fall far outside the destination,
- marks names, hours, prices, durations and locations as AI estimates,
- keeps the plan 'provisional' (see services/planner.py), because an LLM is not
  allowed to be the authority on feasibility or price (TDD 1.2, 4.4).
"""
import logging
import re
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional

from app.agents.itinerary.calculations.filtering import INTEREST_KEYWORDS
from app.agents.itinerary.calculations.geo import haversine_km
from app.agents.itinerary.calculations.scheduling import PACE_CAPACITY
from app.agents.itinerary.providers.base import BaseExperienceProvider, ProviderSearchResult
from app.agents.itinerary.schemas import (
    Activity,
    AvailabilityStatus,
    EvidenceStatus,
    ItineraryRequest,
    OpeningHours,
    PriceBasis,
)
from app.integrations import gemini

logger = logging.getLogger(__name__)

MAX_ITEMS = 24
MIN_DISTANCE_LIMIT_KM = 40.0
SYSTEM = (
    "You are a careful local travel researcher. Suggest only real, currently operating, well-known places. "
    "Never invent places. If you are unsure about a value, use null instead of guessing. Answer with JSON only."
)


def _time(v: Any) -> Optional[time]:
    if not isinstance(v, str):
        return None
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", v)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h == 24 and mi == 0:
        return time(23, 59)
    return time(h, mi) if 0 <= h < 24 and 0 <= mi < 60 else None


def _float(v: Any) -> Optional[float]:
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _price(v: Any) -> Optional[Decimal]:
    if v is None or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None
    return d if d >= 0 else None


def build_prompt(request: ItineraryRequest, count: int) -> str:
    d = request.destination
    where = d.name + (f", {d.country_code}" if d.country_code else "")
    centre = f" (city centre approx. {d.latitude:.4f}, {d.longitude:.4f})" if d.latitude is not None and d.longitude is not None else ""
    interests = ", ".join(request.interests) or "a general mix"
    avoid = ", ".join(request.avoid) or "nothing"
    cats = ", ".join(INTEREST_KEYWORDS.keys())
    kids = f" Travellers include children aged {', '.join(map(str, request.travellers.child_ages))}." if request.travellers.child_ages else ""
    access = " One traveller needs wheelchair access." if "wheelchair" in [n.lower() for n in request.travellers.accessibility_needs] else ""
    return f"""List {count} things to do in {where}{centre} for a trip from {request.start_date} to {request.end_date}.
Interests: {interests}. Avoid: {avoid}.{kids}{access}
Include a mix of the city's best-known sights and a few local experiences, all inside or near the city.

Return JSON: {{"activities": [ ... ]}} where each item has exactly these keys:
- "name": official name of the place or experience
- "category": one of [{cats}]
- "categories": up to 3 of the same values
- "description": one factual sentence
- "address": area or street, or null
- "latitude", "longitude": decimal degrees of the place itself
- "duration_minutes": typical visit length as an integer
- "opening_time", "closing_time": usual daily hours as "HH:MM" (24h), or null if unknown or it varies
- "price_per_person": typical entry price per adult in {request.currency} as a number, 0 if free, null if unknown
- "wheelchair_accessible": true, false or null
- "min_age": minimum age as an integer, or null"""


class GeminiExperienceProvider(BaseExperienceProvider):
    @property
    def name(self) -> str:
        return "Gemini (AI suggestions)"

    async def is_available(self) -> bool:
        return gemini.is_configured()

    async def search(self, request: ItineraryRequest) -> ProviderSearchResult:
        count = min(MAX_ITEMS, max(10, request.trip_days * PACE_CAPACITY[request.pace] * 2))
        try:
            data = await gemini.generate_json(build_prompt(request, count), system=SYSTEM)
        except gemini.GeminiError as e:
            return ProviderSearchResult(limitations=[f"Gemini suggestions unavailable: {e}"])
        items = data.get("activities") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return ProviderSearchResult(limitations=["Gemini returned an unexpected format; no suggestions used."])
        return self.parse(items, request)

    def parse(self, items: List[Any], request: ItineraryRequest) -> ProviderSearchResult:
        d = request.destination
        limit_km = max(MIN_DISTANCE_LIMIT_KM, d.search_radius_km * 2)
        now = datetime.utcnow()
        acts: List[Activity] = []
        dropped_far = dropped_bad = 0
        for i, it in enumerate(items[:MAX_ITEMS]):
            if not isinstance(it, dict) or not str(it.get("name") or "").strip():
                dropped_bad += 1
                continue
            dur = it.get("duration_minutes")
            try:
                dur = int(dur)
            except (TypeError, ValueError):
                dropped_bad += 1
                continue
            dur = max(30, min(dur, 600))
            lat, lon = _float(it.get("latitude")), _float(it.get("longitude"))
            flags = ["ai_suggested", "price_estimated", "hours_estimated", "duration_estimated"]
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                lat = lon = None
                flags.append("coordinates_missing")
            elif d.latitude is not None and d.longitude is not None:
                if haversine_km((d.latitude, d.longitude), (lat, lon)) > limit_km:
                    dropped_far += 1
                    continue
                flags.append("coordinates_estimated")
            o, c = _time(it.get("opening_time")), _time(it.get("closing_time"))
            if not (o and c):
                o = c = None
                flags.append("opening_hours_unknown")
            price = _price(it.get("price_per_person"))
            if price is None:
                flags.append("price_unknown")
            cats = [str(x) for x in (it.get("categories") or []) if isinstance(x, str)][:3]
            cat = str(it.get("category") or (cats[0] if cats else "")) or None
            if cat and cat not in cats:
                cats.insert(0, cat)
            wc = it.get("wheelchair_accessible")
            min_age = it.get("min_age")
            acts.append(Activity(
                activity_id=f"gemini-{i + 1:02d}",
                provider_activity_id=f"gemini-{i + 1:02d}",
                provider_name=self.name,
                name=str(it["name"]).strip()[:120],
                category=cat,
                categories=cats,
                description=(str(it.get("description")).strip()[:300] if it.get("description") else None),
                address=(str(it.get("address")).strip()[:160] if it.get("address") else None),
                latitude=lat,
                longitude=lon,
                duration_minutes=dur,
                duration_status=EvidenceStatus.ESTIMATED,
                opening_hours=OpeningHours(open_time=o, close_time=c,
                                           status=EvidenceStatus.ESTIMATED if o else EvidenceStatus.UNKNOWN,
                                           source=self.name if o else None),
                availability_status=AvailabilityStatus.UNKNOWN,
                price=price,
                currency=request.currency if price is not None else None,
                price_basis=PriceBasis.PER_PERSON,
                price_status=EvidenceStatus.ESTIMATED if price is not None else EvidenceStatus.UNKNOWN,
                wheelchair_accessible=wc if isinstance(wc, bool) else None,
                min_age=min_age if isinstance(min_age, int) and 0 <= min_age <= 21 else None,
                retrieved_at=now,
                is_ai_suggested=True,
                confidence_flags=flags,
            ))
        limitations = [
            "Activities are AI suggestions from Gemini, not live inventory. Names, hours, prices and locations "
            "are estimates; check them before you go."
        ]
        if dropped_far:
            limitations.append(f"{dropped_far} Gemini suggestion(s) were dropped because their location was more than "
                               f"{int(limit_km)} km from {d.name}.")
        if dropped_bad:
            limitations.append(f"{dropped_bad} Gemini suggestion(s) were dropped because required fields were missing.")
        if not acts:
            limitations.append(f"Gemini returned no usable suggestions for {d.name}.")
        return ProviderSearchResult(activities=acts, limitations=limitations)
