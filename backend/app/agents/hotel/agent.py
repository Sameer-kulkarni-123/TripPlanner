"""Hotel Agent definition and execution logic."""
from typing import Any, Dict, List, Optional

from app.agents.hotel.schemas import HotelOption, HotelPreferences, HotelSearchRequest, HotelSearchResult
from app.agents.hotel.services.search import HotelSearchService
from app.agents.hotel.tools import search_hotels
from app.agents.hotel.validation.stay import validate_stay_request


class HotelAgent:
    """
    Hotel Agent Specialist.
    Responsible for accommodation discovery, filtering, comparison, and ranking.
    Interacts with the Orchestrator Agent via shared trip state (`accommodation_options`).
    Recommends options only; it never books or claims a room is reserved.
    """

    def __init__(self, search_service: Optional[HotelSearchService] = None):
        self.search_service = search_service or HotelSearchService()
        self.tools = [search_hotels]

    async def execute(self, state_hotel_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a hotel search given stay requirements from the orchestrator.
        status: "success" | "no_results" | "invalid_request" | "error"
        A new search is required whenever dates, occupancy, or destination change (TDD 8.7 #5).
        """
        try:
            req = HotelSearchRequest(**state_hotel_input)
        except Exception as e:
            return self._response("invalid_request", [], [], [f"Invalid hotel request: {e}"])

        problems = validate_stay_request(req)
        if problems:
            return self._response("invalid_request", [], [], problems)

        try:
            result: HotelSearchResult = await self.search_service.search(req)
        except Exception as e:
            return self._response("error", [], [], [str(e)])

        status = "success" if result.options else "no_results"
        return self._response(status, result.options, result.limitations, [], result.rejected_counts)

    async def rerank(self, state_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Re-rank already retrieved options without a new provider search, e.g. after the itinerary fixes
        activity locations. Expects {"accommodation_options": [...], "preferences": {...}}.
        """
        try:
            options: List[HotelOption] = [HotelOption(**o) for o in state_input.get("accommodation_options", [])]
            prefs = HotelPreferences(**state_input.get("preferences", {}))
            ranked = self.search_service.rerank(options, prefs)
            return self._response("success" if ranked else "no_results", ranked, [], [])
        except Exception as e:
            return self._response("error", [], [], [str(e)])

    @staticmethod
    def _response(status, options, limitations, errors, rejected_counts=None) -> Dict[str, Any]:
        return {
            "status": status,
            "accommodation_options": [opt.model_dump(mode="json") for opt in options],
            "options_count": len(options),
            "limitations": list(limitations),
            "rejected_counts": dict(rejected_counts or {}),
            "errors": list(errors),
        }
