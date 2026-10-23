"""Travel Agent definition and execution logic."""
from typing import Dict, Any, List
from app.agents.travel.schemas import TravelSearchRequest, TransportOption
from app.agents.travel.services.search import TransportSearchService
from app.agents.travel.tools import search_transport_options


class TravelAgent:
    """
    Travel Agent Specialist.
    Responsible for transport discovery, comparison, and ranking.
    Interacts with Orchestrator Agent via shared trip state.
    """

    def __init__(self, search_service: TransportSearchService = None):
        self.search_service = search_service or TransportSearchService()
        self.tools = [search_transport_options]

    async def execute(self, state_travel_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes transport search given extracted trip criteria from the orchestrator.
        """
        try:
            req = TravelSearchRequest(**state_travel_input)
            options: List[TransportOption] = await self.search_service.search_and_rank(req)
            
            return {
                "status": "success",
                "transport_options": [opt.model_dump(mode="json") for opt in options],
                "options_count": len(options),
                "errors": []
            }
        except Exception as e:
            return {
                "status": "error",
                "transport_options": [],
                "options_count": 0,
                "errors": [str(e)]
            }
