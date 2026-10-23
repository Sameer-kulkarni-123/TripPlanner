import logging
from typing import List
from app.agents.travel.schemas import TravelSearchRequest, TransportOption
from app.agents.travel.providers.base import BaseTransportProvider
from app.agents.travel.providers.flight_nuitee import NuiteeFlightProvider
from app.agents.travel.calculations.ranking import rank_transport_options

logger = logging.getLogger(__name__)


class TransportSearchService:
    """
    Coordinates searches across available transport providers (flights, rail, buses),
    filters options based on hard constraints, and ranks them.
    (Section 5.4 in TDD)
    """

    def __init__(self, providers: List[BaseTransportProvider] = None):
        if providers is None:
            self.providers = [NuiteeFlightProvider()]
        else:
            self.providers = providers

    def add_provider(self, provider: BaseTransportProvider):
        self.providers.append(provider)

    async def search_and_rank(self, request: TravelSearchRequest) -> List[TransportOption]:
        all_options: List[TransportOption] = []

        # 1. Query registered providers
        for provider in self.providers:
            try:
                results = await provider.search(request)
                all_options.extend(results)
            except Exception as e:
                logger.error(f"Provider {provider.name} search failed: {e}")

        # 2. Hard constraint filtering (Section 5.2 #8)
        filtered_options: List[TransportOption] = []
        for opt in all_options:
            # Check maximum fare constraint
            if request.constraints.max_fare and opt.price > request.constraints.max_fare:
                continue
            # Check maximum duration constraint
            if request.constraints.max_duration_minutes and opt.duration_minutes > request.constraints.max_duration_minutes:
                continue
            # Check max transfers
            if request.constraints.max_transfers is not None and opt.transfers > request.constraints.max_transfers:
                continue
            # Check arrival deadline
            if request.constraints.must_arrive_before and opt.arrival_time > request.constraints.must_arrive_before:
                continue
            # Check departure window
            if request.constraints.must_depart_after and opt.departure_time < request.constraints.must_depart_after:
                continue

            filtered_options.append(opt)

        # 3. Deterministic ranking (Section 5.10)
        ranked = rank_transport_options(filtered_options, request.preferences)
        return ranked
