"""Normalized schemas for the Itinerary Agent (Technical Design Document, Section 7).

Design rules carried over from the TDD:
- Every activity keeps its provider/source ID, source URL and retrieval timestamp.
- Prices, opening hours, availability and travel times are explicitly marked as
  verified / estimated / unknown. Nothing unknown is silently filled in as fact.
- The agent returns structured data (day plans + validation issues), not prose.
"""
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Pace(str, Enum):
    RELAXED = "relaxed"
    MODERATE = "moderate"
    PACKED = "packed"


class PriceBasis(str, Enum):
    PER_PERSON = "per_person"
    PER_GROUP = "per_group"
    UNKNOWN = "unknown"


class EvidenceStatus(str, Enum):
    """How much we actually know about a fact (opening hours, availability, ...)."""
    VERIFIED = "verified"      # supplied by the provider for the relevant date
    INDICATIVE = "indicative"  # supplied by the provider, but not date-specific
    ESTIMATED = "estimated"    # computed / assumed by application code
    UNKNOWN = "unknown"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ItemKind(str, Enum):
    ACTIVITY = "activity"
    MEAL = "meal"
    REST = "rest"
    ARRIVAL = "arrival"
    DEPARTURE = "departure"


class DayType(str, Enum):
    ARRIVAL = "arrival"
    FULL = "full"
    DEPARTURE = "departure"
    ARRIVAL_AND_DEPARTURE = "arrival_and_departure"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PlanStatus(str, Enum):
    PROVISIONAL = "provisional"
    VALIDATED = "validated"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Request models (what the Orchestrator sends)
# ---------------------------------------------------------------------------


class Destination(BaseModel):
    name: str = Field(description="City or area name, e.g. 'Rome'")
    country_code: Optional[str] = Field(default=None, description="ISO-3166 alpha-2, e.g. 'IT'")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = Field(default=None, description="IANA time zone, e.g. 'Europe/Rome'")
    search_radius_km: float = Field(default=15.0, gt=0, le=200)


class TravellerProfile(BaseModel):
    adults: int = Field(default=1, ge=1)
    children: int = Field(default=0, ge=0)
    child_ages: List[int] = Field(default_factory=list)
    accessibility_needs: List[str] = Field(
        default_factory=list,
        description="e.g. ['wheelchair']. Activities known to be unsuitable are filtered out.",
    )

    @property
    def total(self) -> int:
        return self.adults + self.children


class ActivityBudget(BaseModel):
    max_total: Optional[Decimal] = Field(default=None, description="Max spend on activities for the whole trip")
    max_per_activity: Optional[Decimal] = Field(default=None, description="Max price per person per activity")


class TransportContext(BaseModel):
    """Arrival/departure info from the Travel Agent (may be provisional)."""
    arrival_datetime: Optional[datetime] = Field(default=None, description="Arrival at destination. Naive = destination local time.")
    departure_datetime: Optional[datetime] = Field(default=None, description="Departure from destination. Naive = destination local time.")
    arrival_location: Optional[str] = None
    departure_location: Optional[str] = None
    is_confirmed: bool = Field(default=False, description="True only once the user has selected this transport")
    selected_transport_id: Optional[str] = None


class HotelContext(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_confirmed: bool = False
    selected_accommodation_id: Optional[str] = None


class DailyWindow(BaseModel):
    start: time = time(9, 0)
    end: time = time(20, 30)

    @model_validator(mode="after")
    def _check(self):
        if self.end <= self.start:
            raise ValueError("daily_window.end must be after daily_window.start")
        return self


class ItineraryRequest(BaseModel):
    destination: Destination
    start_date: date
    end_date: date
    travellers: TravellerProfile = Field(default_factory=TravellerProfile)
    interests: List[str] = Field(default_factory=list, description="e.g. ['history', 'food', 'art']")
    avoid: List[str] = Field(default_factory=list, description="Keywords/categories to exclude, e.g. ['nightlife']")
    must_include: List[str] = Field(default_factory=list, description="Provider activity IDs or title keywords the user insists on")
    budget: ActivityBudget = Field(default_factory=ActivityBudget)
    currency: str = "USD"
    language: str = "en"
    pace: Pace = Pace.MODERATE
    daily_window: DailyWindow = Field(default_factory=DailyWindow)
    max_activity_duration_minutes: Optional[int] = Field(default=None, gt=0)
    transport: TransportContext = Field(default_factory=TransportContext)
    hotel: HotelContext = Field(default_factory=HotelContext)

    @model_validator(mode="after")
    def _check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 30:
            raise ValueError("itineraries longer than 31 days are not supported")
        return self

    @property
    def trip_days(self) -> int:
        return (self.end_date - self.start_date).days + 1


# ---------------------------------------------------------------------------
# Activity (normalized provider result) — TDD 7.5
# ---------------------------------------------------------------------------


class OpeningHours(BaseModel):
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    status: EvidenceStatus = EvidenceStatus.UNKNOWN
    source: Optional[str] = None


class Activity(BaseModel):
    activity_id: str = Field(description="Stable internal ID")
    provider_activity_id: str
    provider_name: str
    name: str
    category: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    source_url: Optional[str] = None
    booking_url: Optional[str] = Field(default=None, description="Only when supplied by the provider")
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    duration_minutes: int
    duration_status: EvidenceStatus = EvidenceStatus.INDICATIVE

    opening_hours: OpeningHours = Field(default_factory=OpeningHours)
    availability_status: AvailabilityStatus = AvailabilityStatus.UNKNOWN
    available_dates: Optional[List[date]] = Field(default=None, description="None = not checked")

    price: Optional[Decimal] = None
    currency: Optional[str] = None
    price_basis: PriceBasis = PriceBasis.UNKNOWN
    price_status: EvidenceStatus = EvidenceStatus.UNKNOWN

    rating: Optional[float] = None
    rating_count: Optional[int] = None
    wheelchair_accessible: Optional[bool] = None
    not_suitable_for: Optional[str] = None
    min_age: Optional[int] = None
    cancellable: Optional[bool] = None

    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    is_demo_data: bool = False
    relevance_score: Optional[float] = None
    matched_interests: List[str] = Field(default_factory=list)
    confidence_flags: List[str] = Field(default_factory=list)

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


# ---------------------------------------------------------------------------
# Schedule output
# ---------------------------------------------------------------------------


class TravelEstimate(BaseModel):
    from_label: str
    distance_km: Optional[float] = None
    minutes: int
    mode: str = Field(description="walk | transit | unknown")
    method: str = Field(default="haversine_estimate", description="How it was computed")
    status: EvidenceStatus = EvidenceStatus.ESTIMATED
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class ScheduledItem(BaseModel):
    item_id: str
    kind: ItemKind
    title: str
    start: datetime
    end: datetime
    timezone: Optional[str] = None
    activity_id: Optional[str] = None
    travel_from_previous: Optional[TravelEstimate] = None
    estimated_cost: Optional[Decimal] = None
    notes: List[str] = Field(default_factory=list)


class DayPlan(BaseModel):
    day_number: int
    date: date
    day_type: DayType
    area_label: Optional[str] = None
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    items: List[ScheduledItem] = Field(default_factory=list)
    estimated_cost: Decimal = Decimal("0")
    is_provisional: bool = True
    notes: List[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    severity: Severity
    code: str
    message: str
    day_number: Optional[int] = None
    item_id: Optional[str] = None


class CostSummary(BaseModel):
    currency: str
    total_estimated: Decimal = Decimal("0")
    priced_activities: int = 0
    unpriced_activities: int = 0
    basis_note: str = (
        "Search 'from' prices; not date-specific and not revalidated. "
        "Per-person prices are multiplied by the number of travellers."
    )
    within_budget: Optional[bool] = None
    budget_limit: Optional[Decimal] = None


class ItineraryResult(BaseModel):
    plan_status: PlanStatus
    destination: str
    start_date: date
    end_date: date
    timezone: Optional[str] = None
    days: List[DayPlan] = Field(default_factory=list)
    activities: List[Activity] = Field(default_factory=list, description="Activities used in the schedule")
    alternatives: List[Activity] = Field(default_factory=list, description="Feasible candidates not scheduled")
    cost_summary: CostSummary
    assumptions: List[str] = Field(default_factory=list)
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    revised_days: Optional[List[int]] = Field(default=None, description="Set on targeted revisions")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class RevisionRequest(BaseModel):
    """Focused revision (TDD 7.7 step 4-5)."""
    previous: ItineraryResult
    request: ItineraryRequest = Field(description="The updated trip context")
    days_to_revise: Optional[List[int]] = Field(
        default=None,
        description="Day numbers to rebuild. If omitted, affected days are inferred from what changed.",
    )
    previous_request: Optional[ItineraryRequest] = Field(
        default=None, description="Original context, used to infer which days changed"
    )


class ActivitySearchResult(BaseModel):
    destination: str
    activities: List[Activity] = Field(default_factory=list)
    excluded_count: int = 0
    limitations: List[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
