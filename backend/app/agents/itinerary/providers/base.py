from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agents.itinerary.schemas import Activity, ItineraryRequest


class ProviderSearchResult(BaseModel):
    activities: List[Activity] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class BaseExperienceProvider(ABC):
    """Adapter interface for activity / experience sources (TDD 7.2 #2-4)."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """True if the provider is configured and can be queried."""

    @abstractmethod
    async def search(self, request: ItineraryRequest) -> ProviderSearchResult:
        """Return normalized activities for the destination and trip dates."""

    async def get_available_dates(self, provider_activity_id: str, language: str = "en") -> Optional[List[date]]:
        """Date-specific availability. None = provider cannot tell us."""
        return None
