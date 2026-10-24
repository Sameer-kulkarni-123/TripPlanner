"""API router for the Itinerary Agent."""
from fastapi import APIRouter, HTTPException

from app.agents.itinerary.schemas import (
    ActivitySearchResult,
    ItineraryRequest,
    ItineraryResult,
    RevisionRequest,
)
from app.agents.itinerary.services.planner import ItineraryPlanner

router = APIRouter()
planner = ItineraryPlanner()

_EXAMPLE = {
    "destination": {"name": "Rome", "country_code": "IT", "latitude": 41.8967, "longitude": 12.4822, "timezone": "Europe/Rome"},
    "start_date": "2026-11-20",
    "end_date": "2026-11-23",
    "travellers": {"adults": 2},
    "interests": ["history", "food", "art"],
    "avoid": ["nightlife"],
    "pace": "moderate",
    "currency": "EUR",
    "budget": {"max_total": 400},
    "transport": {"arrival_datetime": "2026-11-20T11:30:00", "departure_datetime": "2026-11-23T18:00:00",
                  "arrival_location": "FCO", "departure_location": "FCO", "is_confirmed": False},
    "hotel": {"name": "Hotel near Pantheon", "latitude": 41.8986, "longitude": 12.4769, "is_confirmed": False},
}


@router.post("/activities", response_model=ActivitySearchResult)
async def search_activities(request: ItineraryRequest):
    """Discover, filter and rank activities for a destination (no scheduling)."""
    try:
        return await planner.search_activities(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan", response_model=ItineraryResult, openapi_extra={
    "requestBody": {"content": {"application/json": {"example": _EXAMPLE}}}})
async def plan_itinerary(request: ItineraryRequest):
    """Build a provisional day-by-day itinerary with validation warnings."""
    try:
        return await planner.plan(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revise", response_model=ItineraryResult)
async def revise_itinerary(revision: RevisionRequest):
    """Targeted revision: rebuild only days affected by changed transport/hotel/preferences."""
    try:
        return await planner.revise(revision)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
