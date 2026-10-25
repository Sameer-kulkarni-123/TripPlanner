"""Hotel Agent tools exposed to LangChain / LangGraph."""
import json
from datetime import date
from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool

from app.agents.hotel.schemas import (
    HotelPreferences,
    HotelSearchConstraints,
    HotelSearchRequest,
    RoomOccupancy,
)
from app.agents.hotel.services.search import HotelSearchService

hotel_service = HotelSearchService()


@tool
async def search_hotels(
    destination: str,
    country_code: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    children_ages: Optional[list[int]] = None,
    rooms: int = 1,
    currency: str = "USD",
    priority: str = "balanced",
    max_total_price: Optional[float] = None,
    min_star_rating: Optional[float] = None,
    refundable_only: bool = False,
) -> str:
    """
    Search, filter, and deterministically rank hotel room/rate options for a stay.
    Args:
        destination: City name (e.g. 'Rome')
        country_code: ISO-2 country code (e.g. 'IT')
        check_in: Check-in date in YYYY-MM-DD format
        check_out: Check-out date in YYYY-MM-DD format
        adults: Adults per room (same for every room)
        children_ages: Ages of children per room (same for every room), if any
        rooms: Number of rooms
        currency: 3-letter currency code for prices
        priority: Ranking priority ('cheapest', 'best_rated', 'location', 'flexible_cancellation', 'balanced')
        max_total_price: Optional maximum TOTAL stay price for all rooms (hard constraint)
        min_star_rating: Optional minimum star rating (hard constraint)
        refundable_only: Only return refundable rates (hard constraint)
    Prices are total-stay prices for all rooms; do not compare them with nightly prices.
    """
    occupancy = RoomOccupancy(adults=adults, children_ages=children_ages or [])
    req = HotelSearchRequest(
        destination=destination,
        country_code=country_code,
        check_in=date.fromisoformat(check_in),
        check_out=date.fromisoformat(check_out),
        rooms=[occupancy.model_copy(deep=True) for _ in range(max(1, rooms))],
        currency=currency,
        preferences=HotelPreferences(priority=priority),
        constraints=HotelSearchConstraints(
            max_total_price=Decimal(str(max_total_price)) if max_total_price is not None else None,
            min_star_rating=min_star_rating,
            refundable_only=refundable_only,
        ),
    )
    result = await hotel_service.search(req)
    if not result.options:
        reasons = "; ".join(result.limitations) or "no matching inventory"
        return f"No suitable hotel options found in {destination} for {check_in} to {check_out}: {reasons}"

    return json.dumps(
        {
            "options": [o.model_dump(mode="json") for o in result.options],
            "limitations": result.limitations,
        },
        indent=2,
    )
