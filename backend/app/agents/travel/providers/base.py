from abc import ABC, abstractmethod
from typing import List
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
