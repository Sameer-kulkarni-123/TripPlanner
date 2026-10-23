"""Travel Agent tools exposed to LangChain / LangGraph."""
import json
from datetime import date
from typing import Optional, List
from langchain_core.tools import tool

from app.agents.travel.schemas import TravelSearchRequest, TravelSearchConstraints, TravelPreferences
from app.agents.travel.services.search import TransportSearchService


transport_service = TransportSearchService()


@tool
async def search_transport_options(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    priority: str = "cheapest",
    max_fare: Optional[float] = None,
    max_duration_minutes: Optional[int] = None,
) -> str:
    """
    Search and rank transport options between origin and destination.
    Args:
        origin: Departure city or airport code (e.g. 'LHR', 'NYC')
        destination: Arrival city or airport code (e.g. 'FCO', 'Rome')
        departure_date: Date in YYYY-MM-DD format
        return_date: Optional return date in YYYY-MM-DD format
        adults: Number of adult passengers
        priority: Ranking priority ('cheapest', 'fastest', 'fewest_transfers', 'balanced')
        max_fare: Optional maximum price filter
        max_duration_minutes: Optional maximum journey duration in minutes
    """
    req = TravelSearchRequest(
        origin=origin,
        destination=destination,
        departure_date=date.fromisoformat(departure_date),
        return_date=date.fromisoformat(return_date) if return_date else None,
        preferences=TravelPreferences(priority=priority),
        constraints=TravelSearchConstraints(
            max_fare=max_fare,
            max_duration_minutes=max_duration_minutes
        )
    )
    req.passengers.adults = adults

    options = await transport_service.search_and_rank(req)
    if not options:
        return f"No feasible transport options found between {origin} and {destination} for {departure_date}."

    return json.dumps([opt.model_dump(mode="json") for opt in options], indent=2)
