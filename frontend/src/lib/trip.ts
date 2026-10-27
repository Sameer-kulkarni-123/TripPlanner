// Client-side orchestration of the three agents.
// This mirrors the order the TDD gives the (not yet built) LangGraph orchestrator:
//   flights (out + back) ‖ itinerary  ->  hotels ranked against the itinerary's stops
//   user picks transport / stay       ->  POST /itinerary/revise with confirmed context
// No numbers are computed here except the trip total, which is a plain sum of API prices.

import { api } from "../api/client";
import type {
  CabinClass,
  GeoPoint,
  HotelOption,
  HotelPriority,
  HotelSearchRequest,
  HotelSearchResult,
  ItineraryRequest,
  ItineraryResult,
  LocalTips,
  Pace,
  TransportOption,
  TravelPriority,
  TravelSearchRequest,
  TravelSearchResult,
} from "../api/types";
import { byIata, type Place } from "../data/places";
import { addDays, daysBetween, num, todayISO } from "./format";

export interface Draft {
  from: Place;
  to: Place;
  start: string;
  end: string;
  adults: number;
  childAges: number[];
  rooms: number;
  pace: Pace;
  interests: string[];
  avoid: string[];
  activityBudget: number | null;
  currency: string;
  flightPriority: TravelPriority;
  cabin: CabinClass;
  hotelPriority: HotelPriority;
  refundableOnly: boolean;
  stepFree: boolean;
}

export function defaultDraft(): Draft {
  const start = addDays(todayISO(), 30);
  return {
    from: byIata("BLR")!,
    to: byIata("JAI")!,
    start,
    end: addDays(start, 3),
    adults: 2,
    childAges: [],
    rooms: 1,
    pace: "moderate",
    interests: ["history", "food", "art"],
    avoid: ["nightlife"],
    activityBudget: 6000,
    currency: "INR",
    flightPriority: "balanced",
    cabin: "economy",
    hotelPriority: "balanced",
    refundableOnly: false,
    stepFree: false,
  };
}

/** Why a draft can't be planned yet, or null. Shared by the landing search and the composer. */
export function draftProblem(d: Draft): string | null {
  const today = todayISO();
  const nights = daysBetween(d.start, d.end);
  if (d.start < today) return "Departure date is in the past.";
  if (nights < 1) return "Return must be at least one day after departure.";
  if (nights > 30) return "Trips are limited to 30 nights.";
  if (daysBetween(today, d.start) > 330) return "Providers only sell up to about 11 months ahead.";
  if (d.from.city === d.to.city && d.from.countryCode === d.to.countryCode) return "Pick a destination different from where you start.";
  return null;
}

// ------------------------------------------------------------------ request builders
export function travelRequest(d: Draft, dir: "out" | "back"): TravelSearchRequest {
  const [o, t, date] = dir === "out" ? [d.from, d.to, d.start] : [d.to, d.from, d.end];
  return {
    origin: o.iata ?? "",
    destination: t.iata ?? "",
    departure_date: date,
    trip_type: "one_way",
    passengers: {
      adults: d.adults,
      children: d.childAges.filter((a) => a >= 2).length,
      infants: d.childAges.filter((a) => a < 2).length,
    },
    currency: d.currency,
    preferences: { priority: d.flightPriority, cabin_class: d.cabin },
  };
}

export function itineraryRequest(d: Draft): ItineraryRequest {
  const p = d.to;
  return {
    destination: {
      name: p.city, country_code: p.countryCode, latitude: p.lat, longitude: p.lon, timezone: p.tz || null,
      // A state or region (Goa, Ladakh) spreads over a much larger area than a city.
      search_radius_km: p.kind === "region" ? 45 : 15,
    },
    start_date: d.start,
    end_date: d.end,
    travellers: {
      adults: d.adults,
      children: d.childAges.length,
      child_ages: d.childAges,
      accessibility_needs: d.stepFree ? ["wheelchair"] : [],
    },
    interests: d.interests,
    avoid: d.avoid,
    must_include: [],
    budget: { max_total: d.activityBudget },
    currency: d.currency,
    language: "en",
    pace: d.pace,
    transport: { is_confirmed: false },
    hotel: { is_confirmed: false },
  };
}

export function hotelRequest(d: Draft, refs: GeoPoint[], priority = d.hotelPriority): HotelSearchRequest {
  const p = d.to;
  const rooms = Array.from({ length: d.rooms }, (_, i) => ({
    adults: Math.max(1, Math.floor(d.adults / d.rooms) + (i < d.adults % d.rooms ? 1 : 0)),
    children_ages: i === 0 ? d.childAges : [],
  }));
  return {
    destination: p.city,
    country_code: p.countryCode,
    check_in: d.start,
    check_out: d.end,
    rooms,
    currency: d.currency,
    guest_nationality: d.from.countryCode,
    constraints: {
      refundable_only: d.refundableOnly,
      accessibility_needs: d.stepFree ? ["wheelchair"] : [],
    },
    preferences: { priority, reference_points: refs },
    max_results: 12,
    max_options_per_hotel: 1,
  };
}

/** Stops the itinerary actually scheduled — used to rank hotels by location (TDD 8.7 #6). */
export function referencePoints(itin: ItineraryResult | null, d: Draft): GeoPoint[] {
  const used = new Set(itin?.days.flatMap((day) => day.items.map((i) => i.activity_id).filter(Boolean)) ?? []);
  const pts = (itin?.activities ?? [])
    .filter((a) => used.has(a.activity_id) && a.latitude != null && a.longitude != null)
    .map((a) => ({ name: a.name.slice(0, 80), latitude: a.latitude!, longitude: a.longitude! }));
  if (pts.length) return pts;
  const p = d.to;
  return [{ name: `${p.city} centre`, latitude: p.lat, longitude: p.lon }];
}

// ------------------------------------------------------------------ lanes
export type LaneKey = "out" | "back" | "itinerary" | "hotels" | "tips";
export type LaneStatus = "waiting" | "running" | "done" | "empty" | "error";
export interface Lane {
  status: LaneStatus;
  ms?: number;
  summary?: string;
  error?: string;
}

export type Settled<T> = { ok: true; data: T } | { ok: false; error: string };

export interface TripData {
  draft: Draft;
  out: Settled<TravelSearchResult>;
  back: Settled<TravelSearchResult>;
  hotels: Settled<HotelSearchResult>;
  itinRequest: ItineraryRequest;
  itin: Settled<ItineraryResult>;
  tips: Settled<LocalTips>;
}

async function timed<T>(fn: () => Promise<T>): Promise<{ r: Settled<T>; ms: number }> {
  const t0 = performance.now();
  try {
    const data = await fn();
    return { r: { ok: true, data }, ms: Math.round(performance.now() - t0) };
  } catch (e) {
    return { r: { ok: false, error: (e as Error).message }, ms: Math.round(performance.now() - t0) };
  }
}

export async function runPlan(
  d: Draft,
  onLane: (k: LaneKey, l: Lane) => void,
  signal?: AbortSignal,
): Promise<TripData> {
  const itinRequest = itineraryRequest(d);
  (["out", "back", "itinerary", "tips"] as LaneKey[]).forEach((k) => onLane(k, { status: "running" }));
  onLane("hotels", { status: "waiting" });

  const flight = (dir: "out" | "back") => {
    const [o, t] = dir === "out" ? [d.from, d.to] : [d.to, d.from];
    const noAirport = [o, t].find((p) => !p.iata);
    if (noAirport) {
      const note = `No airport was found within reach of ${noAirport.city}, so flights for this leg were not searched.`;
      onLane(dir, { status: "empty", ms: 0, summary: "no airport" });
      return Promise.resolve<Settled<TravelSearchResult>>({
        ok: true, data: { options: [], limitations: [note], retrieved_at: new Date().toISOString() },
      });
    }
    return timed(() => api.searchTravel(travelRequest(d, dir), signal)).then(({ r, ms }) => {
      if (!r.ok) onLane(dir, { status: "error", ms, error: r.error });
      else {
        const n = r.data.options.length;
        onLane(dir, { status: n ? "done" : "empty", ms, summary: n ? `${n} fares` : "no fares" });
      }
      return r;
    });
  };

  const outP = flight("out");
  const backP = flight("back");
  const itinP = timed(() => api.planItinerary(itinRequest, signal)).then(({ r, ms }) => {
    if (!r.ok) onLane("itinerary", { status: "error", ms, error: r.error });
    else {
      const stops = r.data.days.reduce((s, day) => s + day.items.filter((i) => i.kind === "activity").length, 0);
      onLane("itinerary", {
        status: r.data.plan_status === "failed" ? "empty" : "done",
        ms,
        summary: `${r.data.days.length} days, ${stops} stops`,
      });
    }
    return r;
  });

  // Hotels wait for the itinerary so they can be ranked by distance to the planned stops.
  const hotelsP = itinP.then(async (itinR) => {
    onLane("hotels", { status: "running" });
    const refs = referencePoints(itinR.ok ? itinR.data : null, d);
    const { r, ms } = await timed(() => api.searchHotels(hotelRequest(d, refs), signal));
    if (!r.ok) onLane("hotels", { status: "error", ms, error: r.error });
    else {
      const n = r.data.options.length;
      onLane("hotels", { status: n ? "done" : "empty", ms, summary: n ? `${n} stays` : "no stays" });
    }
    return r;
  });

  const tipsP = timed(() => api.localTips({ city: d.to.city, country: d.to.country }, signal)).then(({ r, ms }) => {
    if (!r.ok) onLane("tips", { status: "error", ms, error: r.error });
    else {
      const n = r.data.tips.length || r.data.sources.length;
      onLane("tips", { status: n ? "done" : "empty", ms, summary: r.data.tips.length ? `${n} tips` : `${n} pages` });
    }
    return r;
  });

  const [out, back, itin, hotels, tips] = await Promise.all([outP, backP, itinP, hotelsP, tipsP]);
  return { draft: d, out, back, itin, hotels, itinRequest, tips };
}

// ------------------------------------------------------------------ selections -> revised request
export interface Selection {
  out: TransportOption | null;
  back: TransportOption | null;
  hotel: HotelOption | null;
}

export function withSelection(base: ItineraryRequest, s: Selection): ItineraryRequest {
  const transport: ItineraryRequest["transport"] = {
    arrival_datetime: s.out?.arrival_time ?? null,
    arrival_location: s.out ? s.out.destination_name : null,
    departure_datetime: s.back?.departure_time ?? null,
    departure_location: s.back ? s.back.origin_name : null,
    // Confirmed only once the user has chosen both legs (TDD 6.2).
    is_confirmed: Boolean(s.out && s.back),
    selected_transport_id: s.out && s.back ? `${s.out.option_id}+${s.back.option_id}` : null,
  };
  const hotel: ItineraryRequest["hotel"] = s.hotel
    ? {
        name: s.hotel.hotel_name,
        latitude: s.hotel.latitude ?? null,
        longitude: s.hotel.longitude ?? null,
        is_confirmed: true,
        selected_accommodation_id: s.hotel.option_id,
      }
    : { is_confirmed: false };
  return { ...base, transport, hotel };
}

export interface CostLine {
  label: string;
  amount: number | null;
  currency: string;
  note?: string;
}

export function tripCost(d: Draft, s: Selection, itin: ItineraryResult | null) {
  const flights =
    s.out || s.back
      ? (num(s.out?.price) ?? 0) + (num(s.back?.price) ?? 0)
      : null;
  const flightCur = s.out?.currency ?? s.back?.currency ?? d.currency;
  const stay = s.hotel ? num(s.hotel.all_in_price) ?? num(s.hotel.total_price) : null;
  const stayCur = s.hotel?.currency ?? d.currency;
  const acts = itin ? num(itin.cost_summary.total_estimated) : null;
  const actCur = itin?.cost_summary.currency ?? d.currency;
  const lines: CostLine[] = [
    { label: "Flights", amount: flights, currency: flightCur, note: s.out && s.back ? "both legs" : s.out || s.back ? "one leg" : "not chosen" },
    { label: "Stay", amount: stay, currency: stayCur, note: s.hotel ? (num(s.hotel.excluded_charges_total) ? "all-in" : "total") : "not chosen" },
    { label: "Activities", amount: acts, currency: actCur, note: "estimate" },
  ];
  const sameCur = lines.every((l) => l.amount === null || l.currency === d.currency);
  const total = sameCur ? lines.reduce((t, l) => t + (l.amount ?? 0), 0) : null;
  return { lines, total, complete: flights !== null && stay !== null && acts !== null, sameCur };
}
