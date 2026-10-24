"""Adapter for Nuitee / LiteAPI Experiences (tours & activities).

Endpoints (https://docs.liteapi.travel/reference/searchexperiencetours):
  GET /experiences/tours                     - search tours
      required: language, currency
      search:   textSearch  OR  location[latitude] + location[longitude] + location[radiusKm]
      filters:  dateRange[from|to], price[min|max], duration[min|max] (minutes),
                flags (wheelchair, skip-line, ...), sort[field|direction], pagination[limit|offset]
      returns:  {"data": {"meta": {...}, "tours": [ ... ]}}
  GET /experiences/tours/{id}/availability   - available dates for a tour
      returns:  {"data": {"availableDates": [{"date": "YYYY-MM-DD", ...}], ...}}
Errors: 403 means Experiences access is not enabled for the API key.
"""
import logging
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.agents.itinerary.providers.base import BaseExperienceProvider, ProviderSearchResult
from app.agents.itinerary.schemas import (
    Activity,
    AvailabilityStatus,
    EvidenceStatus,
    ItineraryRequest,
    OpeningHours,
    PriceBasis,
)

logger = logging.getLogger(__name__)

DEFAULT_DURATION_MINUTES = 120
_UNIT_TO_MINUTES = {"minute": 1, "minutes": 1, "min": 1, "hour": 60, "hours": 60, "h": 60, "day": 480, "days": 480}


def _parse_time(value: Any) -> Optional[time]:
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", value)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h == 24 and mi == 0:
        return time(23, 59)
    if 0 <= h < 24 and 0 <= mi < 60:
        return time(h, mi)
    return None


def _parse_duration(durations: Any) -> Tuple[int, EvidenceStatus]:
    if isinstance(durations, list) and durations:
        d = durations[0] or {}
        try:
            value = float(d.get("value"))
            factor = _UNIT_TO_MINUTES.get(str(d.get("unit", "")).lower())
            if factor and value > 0:
                return int(round(value * factor)), EvidenceStatus.INDICATIVE
        except (TypeError, ValueError):
            pass
    return DEFAULT_DURATION_MINUTES, EvidenceStatus.ESTIMATED


def _price_basis(description: Optional[str]) -> PriceBasis:
    text = (description or "").lower()
    if any(k in text for k in ("group", "per booking", "private", "vehicle")):
        return PriceBasis.PER_GROUP
    if any(k in text for k in ("person", "per adult", "pp", "each")):
        return PriceBasis.PER_PERSON
    return PriceBasis.UNKNOWN


class NuiteeExperienceProvider(BaseExperienceProvider):
    def __init__(self, api_key: str = "", base_url: str = "", page_size: int = 50, timeout: float = 30.0):
        self.api_key = api_key or settings.NUITEE_API_KEY
        self.base_url = (base_url or settings.NUITEE_API_BASE_URL).rstrip("/")
        self.page_size = page_size
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "Nuitee/LiteAPI Experiences"

    async def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {"accept": "application/json", "X-API-Key": self.api_key}

    def build_query_params(self, request: ItineraryRequest) -> List[Tuple[str, Any]]:
        dest = request.destination
        params: List[Tuple[str, Any]] = [
            ("language", request.language),
            ("currency", request.currency),
            ("dateRange[from]", request.start_date.isoformat()),
            ("dateRange[to]", request.end_date.isoformat()),
            ("sort[field]", "popularity"),
            ("pagination[limit]", self.page_size),
            ("pagination[offset]", 0),
        ]
        if dest.latitude is not None and dest.longitude is not None:
            params += [
                ("location[latitude]", dest.latitude),
                ("location[longitude]", dest.longitude),
                ("location[radiusKm]", dest.search_radius_km),
            ]
        else:
            params.append(("textSearch", dest.name))

        if request.budget.max_per_activity is not None:
            params.append(("price[max]", float(request.budget.max_per_activity)))
        if request.max_activity_duration_minutes:
            params.append(("duration[max]", request.max_activity_duration_minutes))
        needs = {n.lower() for n in request.travellers.accessibility_needs}
        if "wheelchair" in needs:
            params.append(("flags", "wheelchair"))
        return params

    async def search(self, request: ItineraryRequest) -> ProviderSearchResult:
        if not self.api_key:
            return ProviderSearchResult(limitations=["NUITEE_API_KEY not configured; live experience search skipped."])

        url = f"{self.base_url}/experiences/tours"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=self.build_query_params(request), headers=self._headers())
        except Exception as e:  # network errors
            logger.error(f"Nuitee experiences search failed: {e}")
            return ProviderSearchResult(limitations=[f"Nuitee experiences search failed: {e}"])

        if resp.status_code == 403:
            return ProviderSearchResult(limitations=["Nuitee Experiences access is not enabled for this API key (HTTP 403)."])
        if resp.status_code != 200:
            logger.error(f"Nuitee experiences search HTTP {resp.status_code}: {resp.text[:500]}")
            return ProviderSearchResult(limitations=[f"Nuitee experiences search returned HTTP {resp.status_code}."])

        try:
            payload = resp.json()
        except ValueError:
            return ProviderSearchResult(limitations=["Nuitee experiences search returned invalid JSON."])

        activities = self.parse_tours(payload, request)
        limitations = []
        if not activities:
            limitations.append(f"Nuitee returned no experiences for '{request.destination.name}' in the requested dates.")
        return ProviderSearchResult(activities=activities, limitations=limitations)

    def parse_tours(self, payload: Dict[str, Any], request: ItineraryRequest) -> List[Activity]:
        data = payload.get("data") or {}
        tours = data.get("tours") if isinstance(data, dict) else None
        if not isinstance(tours, list):
            return []
        retrieved = datetime.utcnow()
        out: List[Activity] = []
        for tour in tours:
            try:
                out.append(self._parse_tour(tour, request, retrieved))
            except Exception as e:
                logger.debug(f"Skipping unparseable tour: {e}")
        return out

    def _parse_tour(self, tour: Dict[str, Any], request: ItineraryRequest, retrieved: datetime) -> Activity:
        tour_id = str(tour["id"])
        flags: List[str] = []

        coords = tour.get("coordinates") or {}
        lat, lon = coords.get("lat"), coords.get("long")
        if lat is None or lon is None:
            flags.append("coordinates_missing")

        duration, duration_status = _parse_duration(tour.get("durations"))
        if duration_status == EvidenceStatus.ESTIMATED:
            flags.append("duration_estimated")

        oh = tour.get("openingHours") or {}
        open_t, close_t = _parse_time(oh.get("from")), _parse_time(oh.get("to"))
        opening = OpeningHours(
            open_time=open_t,
            close_time=close_t,
            status=EvidenceStatus.INDICATIVE if (open_t and close_t) else EvidenceStatus.UNKNOWN,
            source=self.name if (open_t and close_t) else None,
        )
        if opening.status == EvidenceStatus.UNKNOWN:
            flags.append("opening_hours_unknown")

        price_obj = tour.get("price") or {}
        price: Optional[Decimal] = None
        try:
            if price_obj.get("amount") is not None:
                price = Decimal(str(price_obj["amount"]))
        except (InvalidOperation, TypeError):
            price = None
        basis = _price_basis(tour.get("priceDescription"))
        if price is None:
            flags.append("price_unknown")
        else:
            flags.append("price_is_search_from_price")
        if basis == PriceBasis.UNKNOWN and price is not None:
            flags.append("price_basis_unknown")

        categories = [c.get("name") for c in (tour.get("categories") or []) if c.get("name")]
        locs = tour.get("locations") or []
        address = None
        if locs:
            l0 = locs[0] or {}
            address = ", ".join(p for p in [l0.get("name"), l0.get("city"), l0.get("country")] if p) or None

        tour_flags = {str(f).lower() for f in (tour.get("flags") or [])}
        wheelchair = True if "wheelchair" in tour_flags else None
        not_suitable = tour.get("notSuitableFor")
        if not_suitable and re.search(r"wheelchair|mobility", str(not_suitable), re.I):
            wheelchair = False

        cancel = tour.get("cancellationPolicy") or {}

        return Activity(
            activity_id=f"nuitee-exp-{tour_id}",
            provider_activity_id=tour_id,
            provider_name=self.name,
            name=tour.get("title") or f"Tour {tour_id}",
            category=categories[0] if categories else tour.get("activityType"),
            categories=categories + ([tour["activityType"]] if tour.get("activityType") else []),
            description=tour.get("description"),
            source_url=tour.get("sourceUrl"),
            booking_url=None,  # booking goes through /experiences booking flow; no verified deep link in search
            address=address,
            latitude=lat,
            longitude=lon,
            duration_minutes=duration,
            duration_status=duration_status,
            opening_hours=opening,
            availability_status=AvailabilityStatus.UNKNOWN,
            price=price,
            currency=price_obj.get("currency") or request.currency,
            price_basis=basis,
            price_status=EvidenceStatus.INDICATIVE if price is not None else EvidenceStatus.UNKNOWN,
            rating=tour.get("overallRating"),
            rating_count=tour.get("numberOfRatings"),
            wheelchair_accessible=wheelchair,
            not_suitable_for=not_suitable,
            cancellable=cancel.get("cancellable"),
            retrieved_at=retrieved,
            confidence_flags=flags,
        )

    async def get_available_dates(self, provider_activity_id: str, language: str = "en") -> Optional[List[date]]:
        if not self.api_key:
            return None
        url = f"{self.base_url}/experiences/tours/{provider_activity_id}/availability"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params={"language": language}, headers=self._headers())
            if resp.status_code != 200:
                return None
            data = (resp.json() or {}).get("data") or {}
            dates = []
            for d in data.get("availableDates") or []:
                try:
                    dates.append(date.fromisoformat(d["date"]))
                except (KeyError, ValueError, TypeError):
                    continue
            return dates
        except Exception as e:
            logger.debug(f"Availability lookup failed for tour {provider_activity_id}: {e}")
            return None
