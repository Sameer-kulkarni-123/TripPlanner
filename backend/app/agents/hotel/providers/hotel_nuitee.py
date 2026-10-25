import hashlib
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.agents.hotel.calculations.pricing import (
    all_in_price as calc_all_in,
    money,
    price_per_night,
    sum_excluded_charges,
)
from app.agents.hotel.providers.base import BaseHotelProvider, HotelProviderError
from app.agents.hotel.schemas import (
    AvailabilityStatus,
    BoardType,
    HotelOption,
    HotelSearchRequest,
    TaxOrFee,
)

logger = logging.getLogger(__name__)

_BOARD_CODES = {
    "RO": BoardType.ROOM_ONLY,
    "BB": BoardType.BREAKFAST,
    "HB": BoardType.HALF_BOARD,
    "FB": BoardType.FULL_BOARD,
    "AI": BoardType.ALL_INCLUSIVE,
}


def _to_decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _first_amount(obj: Any) -> Optional[Tuple[Decimal, str]]:
    """LiteAPI returns money either as {"amount","currency"} or as a list of those. Return (amount, currency)."""
    if isinstance(obj, list):
        obj = obj[0] if obj else None
    if not isinstance(obj, dict):
        return None
    amount = _to_decimal(obj.get("amount"))
    currency = obj.get("currency")
    if amount is None or not currency:
        return None
    return amount, str(currency)


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def map_board_type(code: Optional[str], name: Optional[str]) -> BoardType:
    if code and code.upper() in _BOARD_CODES:
        return _BOARD_CODES[code.upper()]
    text = (name or "").lower()
    if "all inclusive" in text or "all-inclusive" in text:
        return BoardType.ALL_INCLUSIVE
    if "full board" in text:
        return BoardType.FULL_BOARD
    if "half board" in text:
        return BoardType.HALF_BOARD
    if "breakfast" in text:
        return BoardType.BREAKFAST
    if "room only" in text:
        return BoardType.ROOM_ONLY
    return BoardType.UNKNOWN


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class NuiteeHotelProvider(BaseHotelProvider):
    """
    Adapter for Nuitee / LiteAPI hotel search.
      1. GET  /data/hotels   (countryCode, cityName, limit) -> static hotel content + hotel IDs
      2. POST /hotels/rates  (hotelIds, checkin, checkout, occupancies, currency, guestNationality)
         -> data[].roomTypes[].rates[]
    Headers: X-API-Key, accept: application/json.
    If the static hotel list comes back empty, falls back to POST /hotels/rates with cityName/countryCode.
    """

    def __init__(self, api_key: str = "", base_url: str = "", max_hotels: int = 0):
        self.api_key = api_key or settings.NUITEE_API_KEY
        self.base_url = (base_url or settings.NUITEE_API_BASE_URL).rstrip("/")
        self.max_hotels = max_hotels or settings.HOTEL_SEARCH_MAX_HOTELS
        self.last_notes: List[str] = []

    @property
    def name(self) -> str:
        return "Nuitee/LiteAPI"

    async def is_available(self) -> bool:
        return bool(self.api_key)

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-Key": self.api_key,
        }

    # ------------------------------------------------------------------ request building
    def _build_rates_payload(
        self, request: HotelSearchRequest, hotel_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "checkin": request.check_in.isoformat(),
            "checkout": request.check_out.isoformat(),
            "occupancies": [
                {"adults": r.adults, "children": list(r.children_ages)} for r in request.rooms
            ],
            "currency": request.currency,
            "guestNationality": request.guest_nationality,
        }
        if hotel_ids:
            payload["hotelIds"] = hotel_ids
        else:
            payload["cityName"] = request.destination
            payload["countryCode"] = request.country_code.upper()
        if request.constraints.refundable_only:
            payload["refundableRatesOnly"] = True
        return payload

    # ------------------------------------------------------------------ search
    async def search(self, request: HotelSearchRequest) -> List[HotelOption]:
        self.last_notes = []
        if not self.api_key:
            raise HotelProviderError("NUITEE_API_KEY is not configured.")

        async with httpx.AsyncClient(timeout=60.0) as client:
            static = await self._fetch_static_hotels(client, request)
            hotel_ids = list(static.keys())
            if not hotel_ids:
                self.last_notes.append(
                    "Hotel list returned no properties; searched rates by city name instead "
                    "(property details may be limited)."
                )
            payload = self._build_rates_payload(request, hotel_ids or None)
            data = await self._post_rates(client, payload)

        # Fallback property info: some responses carry a `hotels` summary array
        for h in data.get("hotels", []) or []:
            if isinstance(h, dict) and h.get("id") and h["id"] not in static:
                static[h["id"]] = self._normalize_static(h)

        return self._parse_rates_response(data, request, static)

    async def _fetch_static_hotels(
        self, client: httpx.AsyncClient, request: HotelSearchRequest
    ) -> Dict[str, Dict[str, Any]]:
        params = {
            "countryCode": request.country_code.upper(),
            "cityName": request.destination,
            "limit": self.max_hotels,
            "offset": 0,
        }
        try:
            resp = await client.get(f"{self.base_url}/data/hotels", params=params, headers=self._headers)
        except httpx.HTTPError as e:
            raise HotelProviderError(f"Nuitee /data/hotels request failed: {e}") from e

        if resp.status_code != 200:
            # Not fatal: rates can still be searched by city. Record it.
            self.last_notes.append(f"Nuitee /data/hotels returned HTTP {resp.status_code}.")
            logger.warning("Nuitee /data/hotels HTTP %s: %s", resp.status_code, resp.text[:300])
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for h in resp.json().get("data", []) or []:
            if isinstance(h, dict) and h.get("id"):
                result[str(h["id"])] = self._normalize_static(h)
        return result

    async def _post_rates(self, client: httpx.AsyncClient, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = await client.post(f"{self.base_url}/hotels/rates", json=payload, headers=self._headers)
        except httpx.HTTPError as e:
            raise HotelProviderError(f"Nuitee /hotels/rates request failed: {e}") from e

        if resp.status_code == 200:
            return resp.json()
        body = resp.text[:500]
        # LiteAPI signals 'nothing available' with an error body rather than an empty list
        if resp.status_code in (400, 404) and "no availability" in body.lower():
            return {"data": []}
        logger.error("Nuitee hotel rates failed: HTTP %s - %s", resp.status_code, body)
        raise HotelProviderError(f"Nuitee /hotels/rates returned HTTP {resp.status_code}: {body}")

    # ------------------------------------------------------------------ parsing
    @staticmethod
    def _normalize_static(h: Dict[str, Any]) -> Dict[str, Any]:
        stars = _float_or_none(h.get("stars", h.get("starRating", h.get("star_rating"))))
        facilities = h.get("hotelFacilities") or h.get("facilities") or []
        return {
            "name": h.get("name") or "Unknown hotel",
            "address": h.get("address"),
            "city": h.get("city"),
            "country_code": h.get("country"),
            "latitude": _float_or_none(h.get("latitude")),
            "longitude": _float_or_none(h.get("longitude")),
            "star_rating": stars if stars else None,  # 0 means 'unrated'
            "guest_rating": _float_or_none(h.get("rating")),
            "main_photo_url": h.get("main_photo") or h.get("thumbnail"),
            "amenities": [str(f) for f in facilities if isinstance(f, str)],
        }

    def _parse_rates_response(
        self, data: Dict[str, Any], request: HotelSearchRequest, static: Dict[str, Dict[str, Any]]
    ) -> List[HotelOption]:
        options: List[HotelOption] = []
        failures = 0
        retrieved_at = datetime.utcnow()

        for hotel in data.get("data", []) or []:
            hotel_id = str(hotel.get("hotelId", ""))
            info = static.get(hotel_id, {})
            for room_type in hotel.get("roomTypes", []) or []:
                try:
                    option = self._parse_room_type(hotel_id, info, room_type, request, retrieved_at)
                    if option:
                        options.append(option)
                    else:
                        failures += 1  # no rates, no usable price, or mixed currencies
                except Exception as err:  # one bad offer must not drop the rest
                    failures += 1
                    logger.debug("Failed to parse hotel offer for %s: %s", hotel_id, err)

        if failures:
            self.last_notes.append(f"{failures} provider offer(s) could not be parsed or had no usable price and were skipped.")
        return options

    def _parse_room_type(
        self,
        hotel_id: str,
        info: Dict[str, Any],
        room_type: Dict[str, Any],
        request: HotelSearchRequest,
        retrieved_at: datetime,
    ) -> Optional[HotelOption]:
        rates = room_type.get("rates", []) or []
        if not rates:
            return None

        # --- Total price across all rooms. Prefer the offer-level total; else sum one rate per occupancy.
        offer_total = _first_amount(room_type.get("offerRetailRate"))
        if offer_total:
            total, currency = offer_total
        else:
            per_room: Dict[Any, Tuple[Decimal, str]] = {}
            for idx, rate in enumerate(rates):
                amt = _first_amount((rate.get("retailRate") or {}).get("total"))
                if not amt:
                    continue
                key = rate.get("occupancyNumber", idx)
                if key not in per_room or amt[0] < per_room[key][0]:
                    per_room[key] = amt  # alternatives for the same room: take cheapest, never add them
            if not per_room:
                return None
            currencies = {c for _, c in per_room.values()}
            if len(currencies) != 1:
                return None
            total = sum((a for a, _ in per_room.values()), Decimal("0"))
            currency = currencies.pop()
        total = money(total)

        # --- Taxes and fees across rates
        fees: List[TaxOrFee] = []
        for rate in rates:
            for t in (rate.get("retailRate") or {}).get("taxesAndFees", []) or []:
                amt = _to_decimal(t.get("amount"))
                if amt is None:
                    continue
                fees.append(
                    TaxOrFee(
                        description=str(t.get("description") or t.get("name") or ""),
                        amount=money(amt),
                        currency=str(t.get("currency") or currency),
                        included_in_total=bool(t.get("included", True)),
                    )
                )
        excluded, foreign_fee = sum_excluded_charges(fees, currency)

        # --- Room / board
        first = rates[0]
        board_type = map_board_type(first.get("boardType"), first.get("boardName"))
        room_names = []
        for r in rates:
            n = r.get("name")
            if n and n not in room_names:
                room_names.append(n)
        max_occ_values = [r.get("maxOccupancy") for r in rates if isinstance(r.get("maxOccupancy"), int)]

        # --- Cancellation (non-refundable if ANY room is non-refundable)
        tags = [(r.get("cancellationPolicies") or {}).get("refundableTag") for r in rates]
        refundable: Optional[bool]
        if any(t == "NRFN" for t in tags):
            refundable = False
        elif tags and all(t == "RFN" for t in tags):
            refundable = True
        else:
            refundable = None
        deadlines = [
            _parse_dt(i.get("cancelTime"))
            for r in rates
            for i in (r.get("cancellationPolicies") or {}).get("cancelPolicyInfos", []) or []
        ]
        deadlines = [d for d in deadlines if d]
        free_until = min(deadlines) if (refundable and deadlines) else None
        if refundable is True:
            cancel_summary = (
                f"Refundable; free cancellation until {free_until.isoformat()}" if free_until else "Refundable"
            )
        elif refundable is False:
            cancel_summary = "Non-refundable"
        else:
            cancel_summary = "Cancellation terms not provided"

        remarks = " | ".join(
            str(x) for r in rates for x in ((r.get("cancellationPolicies") or {}).get("hotelRemarks") or [])
        ) or None
        payment_types = sorted({p for r in rates for p in (r.get("paymentTypes") or [])})

        # --- Build option
        nights = request.nights
        warnings: List[str] = []
        if foreign_fee:
            warnings.append("Some fees payable at the property are in a different currency and are not in all_in_price.")
        if excluded > 0:
            warnings.append(f"{currency} {excluded} of taxes/fees are payable at the property, on top of total_price.")
        if not info:
            warnings.append("Property details (location, rating, amenities) unavailable from provider.")
        if info and info.get("latitude") is None:
            warnings.append("Property coordinates unavailable; distance-based ranking not applied to this option.")
        if refundable is None:
            warnings.append("Cancellation policy missing from provider response.")

        id_seed = "|".join([hotel_id, str(room_type.get("roomTypeId", "")), str(first.get("rateId", ""))])
        supplier = room_type.get("supplier")

        return HotelOption(
            option_id="liteapi-" + hashlib.sha1(id_seed.encode()).hexdigest()[:16],
            provider_hotel_id=hotel_id,
            rate_id=first.get("rateId"),
            offer_id=room_type.get("offerId"),
            room_type_id=str(room_type["roomTypeId"]) if room_type.get("roomTypeId") is not None else None,
            hotel_name=info.get("name") or f"Hotel {hotel_id}",
            address=info.get("address"),
            city=info.get("city"),
            country_code=info.get("country_code"),
            latitude=info.get("latitude"),
            longitude=info.get("longitude"),
            star_rating=info.get("star_rating"),
            guest_rating=info.get("guest_rating"),
            main_photo_url=info.get("main_photo_url"),
            amenities=info.get("amenities", []),
            room_name=", ".join(room_names) or None,
            board_type=board_type,
            board_name=first.get("boardName"),
            max_occupancy=min(max_occ_values) if max_occ_values else None,
            rooms_count=len(request.rooms),
            check_in=request.check_in,
            check_out=request.check_out,
            nights=nights,
            total_price=total,
            currency=currency,
            price_per_night=price_per_night(total, nights),
            taxes_and_fees=fees,
            excluded_charges_total=excluded,
            all_in_price=None if foreign_fee else calc_all_in(total, excluded),
            refundable=refundable,
            cancellation_summary=cancel_summary,
            free_cancellation_until=free_until,
            payment_types=payment_types,
            remarks=remarks,
            availability_status=AvailabilityStatus.AVAILABLE,
            provider_name=f"Nuitee ({supplier})" if supplier else "Nuitee/LiteAPI",
            retrieved_at=retrieved_at,
            warnings=warnings,
        )
