"""Offline demo provider.

Used ONLY when no live provider is configured (no NUITEE_API_KEY) and
ITINERARY_DEMO_MODE is enabled, so the pipeline can be exercised locally.
Every activity is flagged `is_demo_data=True` and every price/hour is marked
ESTIMATED. Never present these results to end users as real inventory.
"""
import math
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

from app.agents.itinerary.providers.base import BaseExperienceProvider, ProviderSearchResult
from app.agents.itinerary.schemas import (
    Activity,
    AvailabilityStatus,
    EvidenceStatus,
    ItineraryRequest,
    OpeningHours,
    PriceBasis,
)

# (title template, categories, duration min, price per person, open, close, north_km, east_km, wheelchair)
_TEMPLATES = [
    ("Old Town walking tour", ["Sightseeing", "History"], 150, "25", time(9, 0), time(18, 0), 0.4, -0.3, True),
    ("Main history museum visit", ["Museums", "History", "Art"], 120, "18", time(9, 30), time(18, 0), 0.8, 0.2, True),
    ("Street food tasting tour", ["Food & Drink", "Culture"], 180, "55", time(11, 0), time(21, 0), -0.6, 0.5, None),
    ("Cathedral & rooftop climb", ["Sightseeing", "Architecture", "History"], 90, "12", time(8, 30), time(17, 30), 0.1, 0.1, False),
    ("Modern art gallery", ["Art", "Museums"], 120, "15", time(10, 0), time(19, 0), 1.9, 1.4, True),
    ("Botanical garden stroll", ["Nature", "Parks"], 90, "8", time(8, 0), time(19, 0), 2.6, -1.8, True),
    ("Local market & cooking class", ["Food & Drink", "Workshops"], 210, "85", time(9, 0), time(16, 0), -1.5, -1.1, None),
    ("Sunset river cruise", ["Sightseeing", "Cruises"], 90, "30", time(17, 0), time(21, 0), -0.2, 1.8, True),
    ("Hilltop viewpoint hike", ["Outdoors", "Nature"], 180, "0", None, None, 4.8, 3.9, False),
    ("Wine & tapas evening", ["Food & Drink", "Nightlife"], 150, "60", time(18, 0), time(23, 0), -0.9, 0.9, None),
    ("Castle & fortress tour", ["History", "Sightseeing", "Architecture"], 150, "22", time(9, 0), time(17, 0), 3.2, 2.7, False),
    ("Bike tour of the waterfront", ["Outdoors", "Sightseeing"], 180, "35", time(9, 0), time(18, 0), -2.4, 2.2, False),
    ("Craft workshop with local artisan", ["Workshops", "Culture", "Art"], 120, "45", time(10, 0), time(18, 0), 1.1, -2.3, True),
    ("Science & technology museum", ["Museums", "Family"], 150, "20", time(9, 0), time(17, 0), -3.1, -2.6, True),
    ("Live music jazz club", ["Nightlife", "Music"], 120, "28", time(20, 0), time(23, 59), -0.4, 0.2, None),
    ("Day trip to the coast", ["Day Trips", "Outdoors", "Nature"], 480, "95", time(8, 0), time(19, 0), -18.0, 9.0, None),
]

# Synthetic centre used when the request has no coordinates (flagged).
_FALLBACK_CENTRE = (0.0, 0.0)


class DemoExperienceProvider(BaseExperienceProvider):
    @property
    def name(self) -> str:
        return "Demo data (offline)"

    async def is_available(self) -> bool:
        return True

    async def search(self, request: ItineraryRequest) -> ProviderSearchResult:
        dest = request.destination
        synthetic = dest.latitude is None or dest.longitude is None
        lat0, lon0 = (_FALLBACK_CENTRE if synthetic else (dest.latitude, dest.longitude))
        city = dest.name

        acts: List[Activity] = []
        now = datetime.utcnow()
        for i, (title, cats, dur, price, o, c, dn, de, wc) in enumerate(_TEMPLATES):
            lat = lat0 + dn / 111.0
            lon = lon0 + de / (111.0 * max(0.2, math.cos(math.radians(lat0))))
            flags = ["demo_data", "price_estimated"]
            if synthetic:
                flags.append("synthetic_coordinates")
            if o is None:
                flags.append("opening_hours_unknown")
            acts.append(
                Activity(
                    activity_id=f"demo-{i + 1:02d}",
                    provider_activity_id=f"demo-{i + 1:02d}",
                    provider_name=self.name,
                    name=f"{city}: {title} (demo)",
                    category=cats[0],
                    categories=cats,
                    description=f"Placeholder activity generated offline for {city}. Not real inventory.",
                    latitude=round(lat, 6),
                    longitude=round(lon, 6),
                    duration_minutes=dur,
                    duration_status=EvidenceStatus.ESTIMATED,
                    opening_hours=OpeningHours(
                        open_time=o,
                        close_time=c,
                        status=EvidenceStatus.ESTIMATED if o else EvidenceStatus.UNKNOWN,
                        source="demo" if o else None,
                    ),
                    availability_status=AvailabilityStatus.UNKNOWN,
                    price=Decimal(price),
                    currency=request.currency,
                    price_basis=PriceBasis.PER_PERSON,
                    price_status=EvidenceStatus.ESTIMATED,
                    rating=round(4.0 + (i % 9) / 10, 1),
                    rating_count=100 + 37 * i,
                    wheelchair_accessible=wc,
                    retrieved_at=now,
                    is_demo_data=True,
                    confidence_flags=flags,
                )
            )
        return ProviderSearchResult(
            activities=acts,
            limitations=[
                "DEMO MODE: no live experiences provider configured (set NUITEE_API_KEY). "
                "Activities, prices and hours are placeholders."
            ],
        )

    async def get_available_dates(self, provider_activity_id: str, language: str = "en") -> Optional[List[date]]:
        return None
