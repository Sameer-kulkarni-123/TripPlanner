from abc import ABC, abstractmethod
from typing import List

from app.agents.hotel.schemas import HotelOption, HotelSearchRequest


class HotelProviderError(Exception):
    """Raised by a provider when a search could not be completed (as opposed to 'no inventory')."""


class BaseHotelProvider(ABC):
    """Abstract base class for all accommodation provider adapters (TDD sections 8.2 and 9)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""

    @abstractmethod
    async def search(self, request: HotelSearchRequest) -> List[HotelOption]:
        """
        Search for hotel room/rate options and return normalized results.
        Return [] when the provider has no inventory; raise HotelProviderError on failures
        so the service can report them instead of presenting them as 'no hotels'.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider API is configured."""
