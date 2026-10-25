from abc import ABC, abstractmethod
from typing import List, Tuple
from app.agents.travel.schemas import TravelSearchRequest, TransportOption


class BaseTransportProvider(ABC):
    """Abstract base class for all transport provider adapters (Section 5.4 in TDD)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""
        pass

    @abstractmethod
    async def search(self, request: TravelSearchRequest) -> List[TransportOption]:
        """Search for transport options and return normalized results."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider API is reachable and configured."""
        pass

    async def search_with_notes(self, request: TravelSearchRequest) -> Tuple[List[TransportOption], List[str]]:
        """Search and also return human-readable notes explaining empty or partial results.

        Providers override this to say *why* nothing came back (missing key, HTTP error,
        no inventory) instead of returning a silent empty list.
        """
        return await self.search(request), []
