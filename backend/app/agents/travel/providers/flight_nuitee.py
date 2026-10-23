import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import httpx
from pydantic import HttpUrl

from app.core.config import settings
from app.agents.travel.schemas import (
    TravelSearchRequest,
    TransportOption,
    TransportMode,
    TransportSegment,
)
from app.agents.travel.providers.base import BaseTransportProvider

logger = logging.getLogger(__name__)


class NuiteeFlightProvider(BaseTransportProvider):
    """
    Adapter for Nuitee / LiteAPI Flight Rates Search API.
    Specifications from OpenAPI definition in nuitee_flights_search_api_documentation.md:
      - Endpoint: POST /flights/rates
      - Headers: X-API-Key, accept: application/json (or text/event-stream)
      - Payload requires `legs`, `adults`, `currency`
      - Legs structure: [{"origin": IATA, "destination": IATA, "date": "YYYY-MM-DD", "direction": "OUTBOUND"|"INBOUND"}]
      - Returns: {"data": [{"journeys": [ ... ]}]}
    """

    def __init__(self, api_key: str = "", base_url: str = ""):
        self.api_key = api_key or settings.NUITEE_API_KEY
        self.base_url = (base_url or settings.NUITEE_API_BASE_URL).rstrip("/")

    @property
    def name(self) -> str:
        return "Nuitee/LiteAPI"

    async def is_available(self) -> bool:
        return bool(self.api_key)

    def _build_request_payload(self, request: TravelSearchRequest) -> Dict[str, Any]:
        """Constructs the legs-based request body compliant with LiteAPI /flights/rates."""
        legs = [
            {
                "origin": request.origin.strip().upper(),
                "destination": request.destination.strip().upper(),
                "date": request.departure_date.isoformat(),
                "direction": "OUTBOUND",
            }
        ]

        # If return date is specified, add INBOUND leg
        if request.return_date:
            legs.append({
                "origin": request.destination.strip().upper(),
                "destination": request.origin.strip().upper(),
                "date": request.return_date.isoformat(),
                "direction": "INBOUND",
            })

        payload: Dict[str, Any] = {
            "legs": legs,
            "adults": request.passengers.adults,
            "children": request.passengers.children,
            "infants": request.passengers.infants,
            "currency": request.currency,
        }

        # Cabin class mapping
        if request.preferences and request.preferences.cabin_class:
            cabin_map = {
                "economy": "ECONOMY",
                "premium_economy": "PREMIUM_ECONOMY",
                "business": "BUSINESS",
                "first": "FIRST",
            }
            mapped_cabin = cabin_map.get(request.preferences.cabin_class.value)
            if mapped_cabin:
                payload["cabinClass"] = mapped_cabin

        # Global filters
        filters: Dict[str, Any] = {}
        if request.constraints:
            if request.constraints.max_fare:
                filters["maxPrice"] = float(request.constraints.max_fare)
            if request.constraints.max_duration_minutes:
                filters["maxDuration"] = request.constraints.max_duration_minutes
            if request.constraints.max_transfers is not None:
                filters["maxStops"] = request.constraints.max_transfers

        if filters:
            payload["filters"] = filters

        # Sort criteria
        sort_by = "price"
        if request.preferences:
            if request.preferences.priority == "fastest":
                sort_by = "duration"
            elif request.preferences.priority == "fewest_transfers":
                sort_by = "stops"

        payload["sort"] = {
            "sortBy": sort_by,
            "sortOrder": "asc",
        }

        return payload

    async def search(self, request: TravelSearchRequest) -> List[TransportOption]:
        """
        Executes flight search via LiteAPI POST /flights/rates.
        """
        if not self.api_key:
            logger.warning("Nuitee API key not set. Skipping live Nuitee flight search.")
            return []

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-Key": self.api_key,
        }

        payload = self._build_request_payload(request)
        url = f"{self.base_url}/flights/rates"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.error(
                        f"Nuitee flight search failed: HTTP {response.status_code} - {response.text}"
                    )
                    return []
                data = response.json()
                return self._parse_nuitee_response(data, request.currency)
        except Exception as e:
            logger.error(f"Error querying Nuitee /flights/rates: {e}")
            return []

    def _parse_nuitee_response(self, data: dict, currency: str) -> List[TransportOption]:
        """
        Normalizes the OpenAPI LiteAPI /flights/rates response into TransportOption models.
        Top-level response: {"data": [{"journeys": [ ... ]}]}
        """
        options: List[TransportOption] = []
        data_batches = data.get("data", [])
        if not isinstance(data_batches, list):
            return []

        for batch in data_batches:
            journeys = batch.get("journeys", [])
            for journey in journeys:
                try:
                    journey_key = journey.get("journeyKey", "")
                    total_duration = journey.get("totalDuration", {}).get("minutes", 0)
                    segments_raw = journey.get("segments", [])
                    offers_raw = journey.get("offers", [])

                    # Parse flight segments
                    parsed_segments: List[TransportSegment] = []
                    for seg in segments_raw:
                        dep_str = seg.get("departureTime")
                        arr_str = seg.get("arrivalTime")
                        carrier_obj = seg.get("carrier", {}) or {}
                        flight_obj = seg.get("flight", {}) or {}
                        
                        seg_model = TransportSegment(
                            departure_location=seg.get("originName") or seg.get("originCode", ""),
                            arrival_location=seg.get("destinationName") or seg.get("destinationCode", ""),
                            departure_time=datetime.fromisoformat(dep_str) if dep_str else datetime.utcnow(),
                            arrival_time=datetime.fromisoformat(arr_str) if arr_str else datetime.utcnow(),
                            duration_minutes=seg.get("duration", {}).get("minutes", 0),
                            carrier_code=carrier_obj.get("marketingCode"),
                            carrier_name=carrier_obj.get("marketingName"),
                            vehicle_or_flight_number=flight_obj.get("marketingNumber"),
                        )
                        parsed_segments.append(seg_model)

                    # Extract primary origin and destination
                    first_seg = parsed_segments[0] if parsed_segments else None
                    last_seg = parsed_segments[-1] if parsed_segments else None

                    origin_name = first_seg.departure_location if first_seg else ""
                    dest_name = last_seg.arrival_location if last_seg else ""
                    dep_time = first_seg.departure_time if first_seg else datetime.utcnow()
                    arr_time = last_seg.arrival_time if last_seg else datetime.utcnow()

                    # Number of transfers = total segments - 1 plus any technical stops
                    transfers_count = max(0, len(parsed_segments) - 1)

                    # Process offers for this journey
                    for offer in offers_raw:
                        offer_id = offer.get("offerId", journey_key)
                        pricing = offer.get("pricing", {}).get("display", {})
                        price_val = Decimal(str(pricing.get("total", "0.00")))
                        offer_curr = pricing.get("currency", currency)

                        baggage_info = offer.get("baggage", {})
                        bag_desc_list = []
                        if baggage_info.get("hasCarryOnBag"):
                            bag_desc_list.append("Carry-on included")
                        if baggage_info.get("hasCheckedBag"):
                            bag_desc_list.append("Checked bag included")
                        for inc in baggage_info.get("included", []):
                            if inc.get("description"):
                                bag_desc_list.append(inc["description"])
                        baggage_summary = ", ".join(bag_desc_list) if bag_desc_list else None

                        provider_code = offer.get("provider", {}).get("code", "LiteAPI")

                        option = TransportOption(
                            option_id=f"liteapi-{offer_id[:24]}",
                            mode=TransportMode.FLIGHT,
                            origin_name=origin_name,
                            destination_name=dest_name,
                            departure_time=dep_time,
                            arrival_time=arr_time,
                            duration_minutes=total_duration,
                            price=price_val,
                            currency=offer_curr,
                            transfers=transfers_count,
                            provider_name=f"Nuitee ({provider_code})",
                            baggage_summary=baggage_summary,
                            segments=parsed_segments,
                            retrieved_at=datetime.utcnow(),
                        )
                        options.append(option)
                except Exception as parse_err:
                    logger.debug(f"Failed to parse journey: {parse_err}")
                    continue

        return options
