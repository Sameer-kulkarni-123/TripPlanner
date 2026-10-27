"""Normalized schemas for the Hotel Agent as defined in Technical Design Document sections 8.2 and 8.5."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


class BoardType(str, Enum):
    """Meal plan, normalized from provider board codes."""
    ROOM_ONLY = "room_only"
    BREAKFAST = "breakfast"
    HALF_BOARD = "half_board"
    FULL_BOARD = "full_board"
    ALL_INCLUSIVE = "all_inclusive"
    UNKNOWN = "unknown"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"      # returned by provider search; not yet pre-booked/locked
    UNVERIFIED = "unverified"    # provider gave no explicit availability signal


class RoomOccupancy(BaseModel):
    """Guests in a single room."""
    adults: int = Field(default=1, ge=1)
    children_ages: List[int] = Field(default_factory=list, description="Age of each child (0-17)")

    @model_validator(mode="after")
    def _check_ages(self):
        if any(a < 0 or a > 17 for a in self.children_ages):
            raise ValueError("children_ages must be between 0 and 17")
        return self

    @property
    def total_guests(self) -> int:
        return self.adults + len(self.children_ages)


class GeoPoint(BaseModel):
    """A location the guests care about (e.g. an itinerary activity or arrival station)."""
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class HotelSearchConstraints(BaseModel):
    """Hard requirements. Options violating any of these are filtered out (TDD 8.2 #4)."""
    max_total_price: Optional[Decimal] = Field(
        default=None, description="Max total stay price for ALL rooms, in the request currency"
    )
    max_price_per_night: Optional[Decimal] = Field(
        default=None, description="Max per-night price for ALL rooms, in the request currency"
    )
    min_star_rating: Optional[float] = Field(default=None, ge=0, le=5)
    refundable_only: bool = False
    required_board_types: List[BoardType] = Field(default_factory=list)
    required_amenities: List[str] = Field(default_factory=list)
    accessibility_needs: List[str] = Field(default_factory=list)
    max_distance_km: Optional[float] = Field(
        default=None, description="Max straight-line distance to the nearest reference point"
    )


class HotelPreferences(BaseModel):
    priority: str = Field(
        default="balanced",
        description="cheapest, best_rated, location, flexible_cancellation, balanced",
    )
    preferred_board_types: List[BoardType] = Field(default_factory=list)
    reference_points: List[GeoPoint] = Field(default_factory=list)


class HotelSearchRequest(BaseModel):
    destination: str = Field(description="City name (e.g. 'Rome')")
    country_code: str = Field(description="ISO-3166 alpha-2 country code (e.g. 'IT')", min_length=2, max_length=2)
    check_in: date
    check_out: date
    rooms: List[RoomOccupancy] = Field(default_factory=lambda: [RoomOccupancy()], min_length=1)
    currency: str = Field(default="USD")
    guest_nationality: str = Field(default="US", description="ISO-2 nationality; affects provider rates")
    constraints: HotelSearchConstraints = Field(default_factory=HotelSearchConstraints)
    preferences: HotelPreferences = Field(default_factory=HotelPreferences)
    max_results: int = Field(default=20, ge=1, le=100)
    max_options_per_hotel: int = Field(default=2, ge=1, le=10)

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def total_guests(self) -> int:
        return sum(r.total_guests for r in self.rooms)


class TaxOrFee(BaseModel):
    description: str = ""
    amount: Decimal
    currency: str
    included_in_total: bool = Field(description="False means payable separately (usually at the property)")


class HotelOption(BaseModel):
    """
    Normalized property + room/rate option (TDD 8.5).
    One option == one bookable room/rate offer; property-level fields are repeated per option.
    """
    # Identifiers
    option_id: str
    provider_hotel_id: str
    rate_id: Optional[str] = None
    offer_id: Optional[str] = None
    room_type_id: Optional[str] = None

    # Property-level details
    hotel_name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    star_rating: Optional[float] = None
    guest_rating: Optional[float] = Field(default=None, description="Provider guest review score, as supplied")
    main_photo_url: Optional[str] = None
    amenities: List[str] = Field(default_factory=list)
    source_url: Optional[HttpUrl] = None

    # Room/rate-level details
    room_name: Optional[str] = None
    board_type: BoardType = BoardType.UNKNOWN
    board_name: Optional[str] = None
    max_occupancy: Optional[int] = None
    rooms_count: int = 1

    # Stay
    check_in: date
    check_out: date
    nights: int

    # Pricing (see calculations/pricing.py). price_basis documents what total_price covers.
    total_price: Decimal = Field(description="Provider total for the whole stay, all rooms, incl. included taxes")
    currency: str
    price_per_night: Decimal
    price_basis: str = "total_stay_all_rooms"
    taxes_and_fees: List[TaxOrFee] = Field(default_factory=list)
    excluded_charges_total: Decimal = Decimal("0.00")
    all_in_price: Optional[Decimal] = Field(
        default=None, description="total_price + excluded charges (only when currencies match)"
    )

    # Policies
    refundable: Optional[bool] = None
    cancellation_summary: Optional[str] = None
    free_cancellation_until: Optional[datetime] = None
    payment_types: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None

    # Provenance / quality
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    provider_name: str
    booking_url: Optional[HttpUrl] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    distance_km_to_reference: Optional[float] = None
    distance_source: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    ranking_score: Optional[float] = None
    confidence_notes: Optional[str] = None


class HotelSearchResult(BaseModel):
    query: HotelSearchRequest
    options: List[HotelOption] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    rejected_counts: dict = Field(
        default_factory=dict, description="constraint name -> number of options it removed"
    )
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
