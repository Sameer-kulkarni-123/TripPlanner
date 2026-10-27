// TypeScript mirrors of the FastAPI / Pydantic models in backend/app/agents/*/schemas.py.
// Decimals arrive as strings and datetimes as ISO strings; see lib/format.ts for parsing.

export type Money = string | number;

// ---------------------------------------------------------------- Travel (agents/travel/schemas.py)
export type TravelPriority = "cheapest" | "fastest" | "fewest_transfers" | "balanced";
export type CabinClass = "economy" | "premium_economy" | "business" | "first";

export interface TravelSearchRequest {
  origin: string;
  destination: string;
  departure_date: string;
  return_date?: string | null;
  trip_type?: "one_way" | "return";
  passengers: { adults: number; children: number; infants: number };
  currency: string;
  constraints?: {
    max_duration_minutes?: number | null;
    max_transfers?: number | null;
    max_fare?: number | null;
  };
  preferences: { priority: TravelPriority; cabin_class?: CabinClass };
}

export interface TransportSegment {
  departure_location: string;
  arrival_location: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  carrier_code?: string | null;
  carrier_name?: string | null;
  vehicle_or_flight_number?: string | null;
}

export interface TransportOption {
  option_id: string;
  mode: string;
  origin_name: string;
  destination_name: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  price: Money;
  currency: string;
  transfers: number;
  provider_name: string;
  booking_url?: string | null;
  retrieved_at: string;
  baggage_summary?: string | null;
  segments: TransportSegment[];
  ranking_score?: number | null;
  confidence_notes?: string | null;
}

export interface TravelSearchResult {
  options: TransportOption[];
  limitations: string[];
  retrieved_at: string;
}

// ---------------------------------------------------------------- Hotel (agents/hotel/schemas.py)
export type HotelPriority = "cheapest" | "best_rated" | "location" | "flexible_cancellation" | "balanced";
export type BoardType = "room_only" | "breakfast" | "half_board" | "full_board" | "all_inclusive" | "unknown";

export interface GeoPoint {
  name: string;
  latitude: number;
  longitude: number;
}

export interface HotelSearchRequest {
  destination: string;
  country_code: string;
  check_in: string;
  check_out: string;
  rooms: { adults: number; children_ages: number[] }[];
  currency: string;
  guest_nationality?: string;
  constraints?: {
    max_total_price?: number | null;
    min_star_rating?: number | null;
    refundable_only?: boolean;
    accessibility_needs?: string[];
  };
  preferences: { priority: HotelPriority; reference_points: GeoPoint[] };
  max_results?: number;
  max_options_per_hotel?: number;
}

export interface TaxOrFee {
  description: string;
  amount: Money;
  currency: string;
  included_in_total: boolean;
}

export interface HotelOption {
  option_id: string;
  provider_hotel_id: string;
  hotel_name: string;
  address?: string | null;
  city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  star_rating?: number | null;
  guest_rating?: number | null;
  main_photo_url?: string | null;
  amenities: string[];
  room_name?: string | null;
  board_type: BoardType;
  board_name?: string | null;
  rooms_count: number;
  check_in: string;
  check_out: string;
  nights: number;
  total_price: Money;
  currency: string;
  price_per_night: Money;
  taxes_and_fees: TaxOrFee[];
  excluded_charges_total: Money;
  all_in_price?: Money | null;
  refundable?: boolean | null;
  cancellation_summary?: string | null;
  free_cancellation_until?: string | null;
  provider_name: string;
  retrieved_at: string;
  distance_km_to_reference?: number | null;
  distance_source?: string | null;
  warnings: string[];
  ranking_score?: number | null;
}

export interface HotelSearchResult {
  options: HotelOption[];
  limitations: string[];
  rejected_counts: Record<string, number>;
  retrieved_at: string;
}

// ---------------------------------------------------------------- Itinerary (agents/itinerary/schemas.py)
export type Pace = "relaxed" | "moderate" | "packed";
export type EvidenceStatus = "verified" | "indicative" | "estimated" | "unknown";
export type ItemKind = "activity" | "meal" | "rest" | "arrival" | "departure";
export type DayType = "arrival" | "full" | "departure" | "arrival_and_departure";
export type Severity = "info" | "warning" | "error";
export type PlanStatus = "provisional" | "validated" | "failed";

export interface ItineraryRequest {
  destination: {
    name: string;
    country_code?: string | null;
    latitude?: number | null;
    longitude?: number | null;
    timezone?: string | null;
    search_radius_km?: number;
  };
  start_date: string;
  end_date: string;
  travellers: { adults: number; children: number; child_ages: number[]; accessibility_needs: string[] };
  interests: string[];
  avoid: string[];
  must_include: string[];
  budget: { max_total?: number | null; max_per_activity?: number | null };
  currency: string;
  language: string;
  pace: Pace;
  transport: {
    arrival_datetime?: string | null;
    departure_datetime?: string | null;
    arrival_location?: string | null;
    departure_location?: string | null;
    is_confirmed: boolean;
    selected_transport_id?: string | null;
  };
  hotel: {
    name?: string | null;
    latitude?: number | null;
    longitude?: number | null;
    is_confirmed: boolean;
    selected_accommodation_id?: string | null;
  };
}

export interface Activity {
  activity_id: string;
  provider_activity_id: string;
  provider_name: string;
  name: string;
  category?: string | null;
  categories: string[];
  description?: string | null;
  source_url?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  duration_minutes: number;
  opening_hours: { open_time?: string | null; close_time?: string | null; status: EvidenceStatus };
  availability_status: "available" | "unavailable" | "unknown";
  price?: Money | null;
  currency?: string | null;
  price_basis: "per_person" | "per_group" | "unknown";
  rating?: number | null;
  rating_count?: number | null;
  is_demo_data: boolean;
  is_ai_suggested?: boolean;
  relevance_score?: number | null;
  matched_interests: string[];
  confidence_flags: string[];
}

export interface TravelEstimate {
  from_label: string;
  distance_km?: number | null;
  minutes: number;
  mode: "none" | "walk" | "transit" | "unknown";
  method: string;
  status: EvidenceStatus;
}

export interface ScheduledItem {
  item_id: string;
  kind: ItemKind;
  title: string;
  start: string;
  end: string;
  timezone?: string | null;
  activity_id?: string | null;
  travel_from_previous?: TravelEstimate | null;
  estimated_cost?: Money | null;
  notes: string[];
}

export interface DayPlan {
  day_number: number;
  date: string;
  day_type: DayType;
  area_label?: string | null;
  available_from?: string | null;
  available_until?: string | null;
  items: ScheduledItem[];
  estimated_cost: Money;
  is_provisional: boolean;
  notes: string[];
}

export interface ValidationIssue {
  severity: Severity;
  code: string;
  message: string;
  day_number?: number | null;
  item_id?: string | null;
}

export interface ItineraryResult {
  plan_status: PlanStatus;
  destination: string;
  start_date: string;
  end_date: string;
  timezone?: string | null;
  days: DayPlan[];
  activities: Activity[];
  alternatives: Activity[];
  cost_summary: {
    currency: string;
    total_estimated: Money;
    priced_activities: number;
    unpriced_activities: number;
    basis_note: string;
    within_budget?: boolean | null;
    budget_limit?: Money | null;
  };
  assumptions: string[];
  validation_issues: ValidationIssue[];
  limitations: string[];
  revised_days?: number[] | null;
  generated_at: string;
}

// ---------------------------------------------------------------- Places + assistant (api/places.py, api/assistant.py)
export interface PlaceResult {
  city: string;
  region?: string | null;
  country?: string | null;
  country_code: string;
  latitude: number;
  longitude: number;
  timezone?: string | null;
  population?: number | null;
  kind?: "city" | "region";
  base?: string | null;
  source?: string;
  airport?: { code: string; name: string; distance_km: number } | null;
}

export interface TripDraftResult {
  destination: PlaceResult | null;
  origin: PlaceResult | null;
  start_date: string | null;
  end_date: string | null;
  adults: number | null;
  children_ages: number[];
  interests: string[];
  avoid: string[];
  pace: Pace | null;
  activity_budget: number | null;
  currency: string | null;
  wheelchair: boolean;
  missing: string[];
  notes: string[];
}

export interface Health {
  status: string;
  service: string;
  version: string;
  gemini_configured?: boolean;
  nuitee_configured?: boolean;
  tavily_configured?: boolean;
}

// ---------------------------------------------------------------- Local tips (api/insights.py)
export interface TipSource { title: string; url: string; domain: string }
export interface LocalTip {
  category: "scams" | "getting_around" | "money" | "culture" | "safety" | "food" | "timing";
  category_label: string;
  title: string;
  advice: string;
  sources: TipSource[];
}
export interface LocalTips {
  destination: string;
  summary: string | null;
  tips: LocalTip[];
  sources: (TipSource & { snippet: string })[];
  limitations: string[];
  method: string;
}
