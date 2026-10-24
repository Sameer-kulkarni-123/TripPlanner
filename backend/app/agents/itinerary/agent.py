"""Itinerary Agent definition and execution logic (TDD Section 7).

The orchestrator calls `execute()` with a dict (or `execute_from_state()` with the
shared TripState) and receives structured results; `revise()` performs targeted
revisions when transport, hotel, or preferences change.
"""
from datetime import date, datetime
from typing import Any, Dict, Optional

from app.agents.itinerary.schemas import ItineraryRequest, RevisionRequest
from app.agents.itinerary.services.planner import ItineraryPlanner
from app.agents.itinerary.tools import plan_itinerary, search_activities


def _as_date(v: Any) -> Optional[date]:
    if v is None or isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    return date.fromisoformat(str(v)[:10])


def request_from_trip_state(state: Dict[str, Any]) -> ItineraryRequest:
    """Map the orchestrator's shared TripState (orchestrator/state.py) to an ItineraryRequest.

    The selected transport option (if any) supplies arrival/departure context; otherwise the
    top-ranked option is used and marked provisional (TDD 6.2).
    """
    dest = state.get("destination") or {}
    dates = state.get("date_constraints") or {}
    travellers = state.get("traveller_details") or {}
    budget = state.get("budget") or {}
    prefs = state.get("preferences") or {}

    transport: Dict[str, Any] = {}
    options = state.get("transport_options") or []
    selected_id = state.get("selected_transport_id")
    chosen = next((o for o in options if o.get("option_id") == selected_id), None) if selected_id else None
    is_confirmed = chosen is not None
    if chosen is None and options:
        chosen = options[0]
    if chosen:
        transport = {
            "arrival_datetime": chosen.get("arrival_time"),
            "arrival_location": chosen.get("destination_name"),
            "is_confirmed": is_confirmed,
            "selected_transport_id": chosen.get("option_id") if is_confirmed else None,
        }
    if dates.get("return_departure_time"):
        transport["departure_datetime"] = dates["return_departure_time"]

    hotel: Dict[str, Any] = {}
    acc_id = state.get("selected_accommodation_id")
    for h in state.get("accommodation_options") or []:
        if acc_id and h.get("option_id") == acc_id:
            hotel = {
                "name": h.get("name"), "latitude": h.get("latitude"), "longitude": h.get("longitude"),
                "is_confirmed": True, "selected_accommodation_id": acc_id,
            }
            break

    return ItineraryRequest(
        destination={
            "name": dest.get("name") or dest.get("city") or "",
            "country_code": dest.get("country_code"),
            "latitude": dest.get("latitude"),
            "longitude": dest.get("longitude"),
            "timezone": dest.get("timezone"),
        },
        start_date=_as_date(dates.get("start_date") or dates.get("departure_date")),
        end_date=_as_date(dates.get("end_date") or dates.get("return_date") or dates.get("start_date")),
        travellers={
            "adults": travellers.get("adults", 1),
            "children": travellers.get("children", 0),
            "child_ages": travellers.get("child_ages", []),
            "accessibility_needs": travellers.get("accessibility_needs", []),
        },
        interests=prefs.get("interests", []),
        avoid=prefs.get("avoid", []),
        must_include=prefs.get("must_include", []),
        pace=prefs.get("pace", "moderate"),
        currency=budget.get("currency", "USD"),
        budget={
            "max_total": budget.get("activities_max") or budget.get("activities"),
            "max_per_activity": budget.get("max_per_activity"),
        },
        transport=transport,
        hotel=hotel,
    )


class ItineraryAgent:
    """
    Itinerary Agent Specialist.
    Discovers experiences (Nuitee), filters and scores them, builds a provisional
    day-by-day schedule, validates it mechanically and reports uncertainty.
    """

    def __init__(self, planner: Optional[ItineraryPlanner] = None):
        self.planner = planner or ItineraryPlanner()
        self.tools = [search_activities, plan_itinerary]

    async def execute(self, itinerary_input: Dict[str, Any]) -> Dict[str, Any]:
        try:
            req = ItineraryRequest(**itinerary_input)
            result = await self.planner.plan(req)
            return {
                "status": "success" if result.plan_status != "failed" else "error",
                "itinerary": result.model_dump(mode="json"),
                "errors": [] if result.plan_status != "failed" else result.limitations,
            }
        except Exception as e:
            return {"status": "error", "itinerary": {}, "errors": [str(e)]}

    async def execute_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph node-style entrypoint: returns a partial TripState update."""
        agent_status = dict(state.get("agent_status") or {})
        try:
            req = request_from_trip_state(state)
            result = await self.planner.plan(req)
            agent_status["itinerary"] = result.plan_status.value
            issues = list(state.get("validation_issues") or [])
            issues += [{"agent": "itinerary", **i.model_dump(mode="json")} for i in result.validation_issues
                       if i.severity != "info"]
            return {
                "itinerary": result.model_dump(mode="json"),
                "agent_status": agent_status,
                "validation_issues": issues,
            }
        except Exception as e:
            agent_status["itinerary"] = "failed"
            return {"agent_status": agent_status,
                    "validation_issues": list(state.get("validation_issues") or []) + [
                        {"agent": "itinerary", "severity": "error", "code": "itinerary_agent_failed", "message": str(e)}]}

    async def revise(self, revision_input: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rev = RevisionRequest(**revision_input)
            result = await self.planner.revise(rev)
            return {"status": "success", "itinerary": result.model_dump(mode="json"), "errors": []}
        except Exception as e:
            return {"status": "error", "itinerary": {}, "errors": [str(e)]}
