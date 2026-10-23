"""Normalized schemas for Travel Agent as defined in Technical Design Document section 5.8."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class TransportMode(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"
    FERRY = "ferry"
    OTHER = "other"


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class PassengerRequirements(BaseModel):
    adults: int = Field(default=1, ge=1)
    children: int = Field(default=0, ge=0)
    infants: int = Field(default=0, ge=0)


class TravelSearchConstraints(BaseModel):
    max_duration_minutes: Optional[int] = None
    max_transfers: Optional[int] = None
    max_fare: Optional[Decimal] = None
    must_arrive_before: Optional[datetime] = None
    must_depart_after: Optional[datetime] = None
    accessibility_needs: Optional[List[str]] = Field(default_factory=list)


class TravelPreferences(BaseModel):
    priority: str = Field(default="cheapest", description="cheapest, fastest, fewest_transfers, balanced")
    cabin_class: Optional[CabinClass] = CabinClass.ECONOMY
    preferred_carriers: Optional[List[str]] = Field(default_factory=list)
    avoid_carriers: Optional[List[str]] = Field(default_factory=list)


class TravelSearchRequest(BaseModel):
    origin: str = Field(description="Origin city, airport code, or station name (e.g., LHR, London)")
    destination: str = Field(description="Destination city, airport code, or station name (e.g., FCO, Rome)")
    departure_date: date
    return_date: Optional[date] = None
    trip_type: str = Field(default="one_way", description="one_way or return")
    passengers: PassengerRequirements = Field(default_factory=PassengerRequirements)
    currency: str = Field(default="USD")
    constraints: TravelSearchConstraints = Field(default_factory=TravelSearchConstraints)
    preferences: TravelPreferences = Field(default_factory=TravelPreferences)


class TransportSegment(BaseModel):
    departure_location: str
    arrival_location: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    carrier_code: Optional[str] = None
    carrier_name: Optional[str] = None
    vehicle_or_flight_number: Optional[str] = None
    cabin_class: Optional[str] = None


class TransportOption(BaseModel):
    """Normalized transport option model matching Section 5.8 of TDD."""
    option_id: str
    mode: TransportMode
    origin_name: str
    destination_name: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    price: Decimal
    currency: str
    transfers: int = 0
    provider_name: str
    booking_url: Optional[HttpUrl] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    baggage_summary: Optional[str] = None
    segments: List[TransportSegment] = Field(default_factory=list)
    ranking_score: Optional[float] = None
    confidence_notes: Optional[str] = None


class TravelSearchResult(BaseModel):
    query: TravelSearchRequest
    options: List[TransportOption] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
