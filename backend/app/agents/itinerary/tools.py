"""Itinerary Agent tools exposed to LangChain / LangGraph."""
import json
from datetime import date
from typing import List, Optional

from langchain_core.tools import tool

from app.agents.itinerary.schemas import ItineraryRequest
from app.agents.itinerary.services.planner import ItineraryPlanner

_planner = ItineraryPlanner()


def _build_request(
    destination: str, start_date: str, end_date: str, interests: Optional[List[str]], adults: int,
    pace: str, currency: str, latitude: Optional[float], longitude: Optional[float], timezone: Optional[str],
    max_total_budget: Optional[float], arrival_datetime: Optional[str], departure_datetime: Optional[str],
) -> ItineraryRequest:
    return ItineraryRequest(
        destination={"name": destination, "latitude": latitude, "longitude": longitude, "timezone": timezone},
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date),
        interests=interests or [],
        travellers={"adults": adults},
        pace=pace,
        currency=currency,
        budget={"max_total": max_total_budget},
        transport={"arrival_datetime": arrival_datetime, "departure_datetime": departure_datetime},
    )


@tool
async def search_activities(
    destination: str,
    start_date: str,
    end_date: str,
    interests: Optional[List[str]] = None,
    adults: int = 1,
    currency: str = "USD",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> str:
    """
    Find and rank activities/experiences at a destination (no scheduling).
    Args:
        destination: City name, e.g. 'Rome'
        start_date / end_date: Trip dates, YYYY-MM-DD
        interests: e.g. ['history', 'food']
        adults: Number of adult travellers
        currency: ISO currency code for prices
        latitude / longitude: Optional destination centre for radius search
    """
    req = _build_request(destination, start_date, end_date, interests, adults, "moderate", currency,
                         latitude, longitude, None, None, None, None)
    res = await _planner.search_activities(req)
    return json.dumps(res.model_dump(mode="json"), indent=2)


@tool
async def plan_itinerary(
    destination: str,
    start_date: str,
    end_date: str,
    interests: Optional[List[str]] = None,
    adults: int = 1,
    pace: str = "moderate",
    currency: str = "USD",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[str] = None,
    max_total_budget: Optional[float] = None,
    arrival_datetime: Optional[str] = None,
    departure_datetime: Optional[str] = None,
) -> str:
    """
    Build a provisional day-by-day itinerary with time blocks, travel buffers, meals and rest,
    plus cost estimates and validation warnings. Schedules are deterministic; unknown hours,
    prices or availability are flagged, never invented.
    Args:
        destination: City name
        start_date / end_date: YYYY-MM-DD
        interests: e.g. ['art', 'food']
        adults: Number of adults
        pace: 'relaxed', 'moderate' or 'packed'
        currency: ISO currency code
        latitude / longitude: Optional destination centre
        timezone: IANA zone, e.g. 'Europe/Rome'
        max_total_budget: Max spend on activities for the whole trip
        arrival_datetime / departure_datetime: ISO datetimes from the selected transport
    """
    req = _build_request(destination, start_date, end_date, interests, adults, pace, currency, latitude,
                         longitude, timezone, max_total_budget, arrival_datetime, departure_datetime)
    res = await _planner.plan(req)
    return json.dumps(res.model_dump(mode="json"), indent=2)
