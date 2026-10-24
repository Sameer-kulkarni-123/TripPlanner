"""Deterministic day-by-day scheduler (TDD 7.2 #6-7, 7.4).

Pipeline:
  1. compute_day_windows  - usable time per day after arrival/departure buffers
  2. build_schedule       - for each day, greedily grow a geographically tight group
                            of high-scoring activities, then search all visiting
                            orders (<= 4 activities -> <= 24 permutations) for the
                            one with least travel + idle time that satisfies
                            opening hours, lunch, rest and the day window.
No LLM is involved; every number here is reproducible.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import permutations
from typing import Dict, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agents.itinerary.calculations.geo import centroid, estimate_travel, haversine_km
from app.agents.itinerary.calculations.filtering import is_must_include
from app.agents.itinerary.schemas import (
    Activity,
    DayPlan,
    DayType,
    EvidenceStatus,
    ItemKind,
    ItineraryRequest,
    Pace,
    PriceBasis,
    ScheduledItem,
    TravelEstimate,
)

ARRIVAL_BUFFER_MIN = 120      # deplane, baggage, transfer to hotel / drop bags
DEPARTURE_BUFFER_MIN = 180    # transfer to station/airport + check-in
TRAVEL_SLACK_MIN = 10         # added on top of every estimated transfer
MIN_USEFUL_WINDOW_MIN = 90
MINUTES_PER_SLOT = 150

LUNCH_FROM, LUNCH_LATEST_START, LUNCH_MUST_END_BY = time(12, 0), time(14, 0), time(14, 30)
LUNCH_MIN = 60
DINNER_FROM, DINNER_MIN = time(19, 0), 75
LONG_ACTIVITY_MIN = 300       # e.g. day trips: assume lunch is taken during the activity

PACE_CAPACITY = {Pace.RELAXED: 2, Pace.MODERATE: 3, Pace.PACKED: 4}
REST_AFTER_MIN = {Pace.RELAXED: 150, Pace.MODERATE: 240, Pace.PACKED: None}
REST_MIN = {Pace.RELAXED: 45, Pace.MODERATE: 30, Pace.PACKED: 0}
MAX_CANDIDATES_PER_SLOT = 25
DISTANCE_PENALTY_PER_KM = 0.04
NO_COORDS_PENALTY = 0.3


# ---------------------------------------------------------------------------
# Time zone helpers
# ---------------------------------------------------------------------------


def resolve_tz(name: Optional[str]) -> Optional[ZoneInfo]:
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def to_local(dt: Optional[datetime], tz: Optional[ZoneInfo]) -> Optional[datetime]:
    """Naive datetimes are treated as destination-local time."""
    if dt is None:
        return None
    if tz is None:
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    return dt.astimezone(tz) if dt.tzinfo else dt.replace(tzinfo=tz)


def at(d: date, t: time, tz: Optional[ZoneInfo]) -> datetime:
    return datetime.combine(d, t, tzinfo=tz)


# ---------------------------------------------------------------------------
# Day windows
# ---------------------------------------------------------------------------


@dataclass
class DayWindow:
    day_number: int
    date: date
    day_type: DayType
    start: Optional[datetime]
    end: Optional[datetime]
    capacity: int
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None
    notes: List[str] = field(default_factory=list)

    @property
    def minutes(self) -> int:
        if not self.start or not self.end:
            return 0
        return max(0, int((self.end - self.start).total_seconds() // 60))


def compute_day_windows(request: ItineraryRequest) -> Tuple[List[DayWindow], List[str]]:
    tz = resolve_tz(request.destination.timezone)
    assumptions: List[str] = []
    if request.destination.timezone and tz is None:
        assumptions.append(f"Unrecognised time zone '{request.destination.timezone}'; times are naive local times.")
    elif tz is None:
        assumptions.append("Destination time zone not supplied; all times are naive destination-local times.")

    arrival = to_local(request.transport.arrival_datetime, tz)
    departure = to_local(request.transport.departure_datetime, tz)
    status = "confirmed" if request.transport.is_confirmed else "provisional (not yet selected by the user)"
    if arrival:
        assumptions.append(f"Arrival {arrival.isoformat()} taken from {status} transport; {ARRIVAL_BUFFER_MIN} min buffer before first activity.")
    else:
        assumptions.append(f"No arrival time supplied; day 1 assumes the traveller is free from {request.daily_window.start.strftime('%H:%M')}.")
    if departure:
        assumptions.append(f"Departure {departure.isoformat()} taken from {status} transport; activities end {DEPARTURE_BUFFER_MIN} min before.")
    else:
        assumptions.append(f"No departure time supplied; last day assumes activities until {request.daily_window.end.strftime('%H:%M')}.")

    pace_cap = PACE_CAPACITY[request.pace]
    windows: List[DayWindow] = []
    for i in range(request.trip_days):
        d = request.start_date + timedelta(days=i)
        start = at(d, request.daily_window.start, tz)
        end = at(d, request.daily_window.end, tz)
        is_arr = arrival is not None and d == arrival.date()
        is_dep = departure is not None and d == departure.date()
        day_type = (
            DayType.ARRIVAL_AND_DEPARTURE if is_arr and is_dep
            else DayType.ARRIVAL if is_arr or (arrival is None and i == 0)
            else DayType.DEPARTURE if is_dep or (departure is None and i == request.trip_days - 1 and request.trip_days > 1)
            else DayType.FULL
        )
        notes: List[str] = []
        if arrival and d < arrival.date():
            notes.append("Traveller has not arrived yet on this date.")
            start = end = None
        if departure and start and d > departure.date():
            notes.append("Traveller has already departed on this date.")
            start = end = None
        if start and is_arr:
            start = max(start, arrival + timedelta(minutes=ARRIVAL_BUFFER_MIN))
        if end and is_dep:
            end = min(end, departure - timedelta(minutes=DEPARTURE_BUFFER_MIN))

        w = DayWindow(i + 1, d, day_type, start, end, 0, arrival if is_arr else None, departure if is_dep else None, notes)
        if start and end and w.minutes >= MIN_USEFUL_WINDOW_MIN:
            w.capacity = max(1, min(pace_cap, w.minutes // MINUTES_PER_SLOT))
        elif start or end:
            w.notes.append("Not enough free time for activities on this day.")
        windows.append(w)
    return windows, assumptions


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------


def activity_cost(a: Activity, travellers: int, currency: Optional[str] = None) -> Optional[Decimal]:
    """Estimated cost for the party; None if unpriced or priced in another currency."""
    if a.price is None:
        return None
    if currency and a.currency and a.currency.upper() != currency.upper():
        return None
    if a.price_basis == PriceBasis.PER_GROUP:
        return a.price
    return a.price * travellers  # per-person, or unknown basis (flagged) treated conservatively


# ---------------------------------------------------------------------------
# Single-day simulation
# ---------------------------------------------------------------------------


def _pt(a: Activity) -> Optional[Tuple[float, float]]:
    return (a.latitude, a.longitude) if a.has_coordinates else None


@dataclass
class _Sim:
    items: List[ScheduledItem]
    travel_min: int
    idle_min: int

    @property
    def cost(self) -> float:
        return self.travel_min + 0.5 * self.idle_min


def _simulate(
    w: DayWindow, order: Sequence[Activity], request: ItineraryRequest, hotel_pt, tz_name: Optional[str]
) -> Optional[_Sim]:
    tz = w.start.tzinfo
    d = w.date
    pace = request.pace
    lunch_from, lunch_latest, lunch_end_by = at(d, LUNCH_FROM, tz), at(d, LUNCH_LATEST_START, tz), at(d, LUNCH_MUST_END_BY, tz)
    lunch_done = not (w.start <= at(d, time(13, 0), tz) and w.end >= lunch_end_by)
    items: List[ScheduledItem] = []
    cursor = w.start
    prev_pt, prev_label = hotel_pt, (request.hotel.name or "hotel") if hotel_pt else None
    since_break = travel_total = idle = 0
    seq = 0

    def add(kind, title, s, e, **kw):
        nonlocal seq
        seq += 1
        items.append(ScheduledItem(item_id=f"d{w.day_number}-{seq:02d}", kind=kind, title=title, start=s, end=e, timezone=tz_name, **kw))

    def place_lunch():
        nonlocal cursor, lunch_done, since_break, idle
        s = max(cursor, lunch_from)
        if s > lunch_latest:
            lunch_done = True
            return
        idle += int((s - cursor).total_seconds() // 60)
        add(ItemKind.MEAL, "Lunch break", s, s + timedelta(minutes=LUNCH_MIN), notes=["Time reserved; venue not selected."])
        cursor, lunch_done, since_break = s + timedelta(minutes=LUNCH_MIN), True, 0

    for idx, a in enumerate(order):
        if not lunch_done and cursor >= lunch_from:
            place_lunch()

        a_pt = _pt(a)
        if prev_label is None:
            dist, tmin, mode, travel = None, 0, "none", None
        else:
            dist, tmin, mode = estimate_travel(prev_pt, a_pt)
            travel = TravelEstimate(
                from_label=prev_label, distance_km=dist, minutes=tmin, mode=mode,
                method="haversine x1.3 route factor" if mode != "unknown" else "default (coordinates missing)",
                status=EvidenceStatus.ESTIMATED if mode != "unknown" else EvidenceStatus.UNKNOWN,
            )
        gap = tmin + (TRAVEL_SLACK_MIN if tmin > 0 else 0)

        def window_for(cur):
            s = cur + timedelta(minutes=gap)
            oh = a.opening_hours
            o = c = None
            if oh.open_time and oh.close_time:
                o, c = at(d, oh.open_time, tz), at(d, oh.close_time, tz)
                if c <= o:
                    c += timedelta(days=1)
                s = max(s, o)
            return s, s + timedelta(minutes=a.duration_minutes), c

        start, end, close = window_for(cursor)
        if not lunch_done and end > lunch_latest and a.duration_minutes < LONG_ACTIVITY_MIN:
            place_lunch()
            start, end, close = window_for(cursor)
        if close is not None and end > close:
            return None
        if end > w.end:
            return None

        idle += max(0, int((start - cursor).total_seconds() // 60) - gap)
        travel_total += tmin
        notes = []
        if a.opening_hours.status == EvidenceStatus.UNKNOWN:
            notes.append("Opening hours unknown - verify before visiting.")
        if a.duration_minutes >= LONG_ACTIVITY_MIN and not lunch_done:
            notes.append("Long activity: plan lunch during it.")
            lunch_done = True
        add(
            ItemKind.ACTIVITY, a.name, start, end,
            activity_id=a.activity_id, travel_from_previous=travel,
            estimated_cost=activity_cost(a, request.travellers.total, request.currency), notes=notes,
        )
        cursor, prev_pt, prev_label = end, a_pt, a.name
        since_break += a.duration_minutes

        # Lunch doubles as the break when we are already inside the lunch window.
        if not lunch_done and lunch_from <= cursor <= lunch_latest and idx < len(order) - 1:
            place_lunch()

        rest_after = REST_AFTER_MIN[pace]
        if rest_after and since_break >= rest_after and idx < len(order) - 1:
            r_end = cursor + timedelta(minutes=REST_MIN[pace])
            if r_end <= w.end:
                add(ItemKind.REST, "Rest / free time", cursor, r_end)
                cursor, since_break = r_end, 0

    if not lunch_done and cursor <= lunch_latest:
        place_lunch()

    dinner_s = max(cursor, at(d, DINNER_FROM, tz))
    if dinner_s + timedelta(minutes=DINNER_MIN) <= w.end:
        add(ItemKind.MEAL, "Dinner", dinner_s, dinner_s + timedelta(minutes=DINNER_MIN), notes=["Time reserved; venue not selected."])

    items.sort(key=lambda it: it.start)
    return _Sim(items, travel_total, idle)


def schedule_day(
    w: DayWindow, acts: List[Activity], request: ItineraryRequest, hotel_pt, tz_name: Optional[str]
) -> Optional[_Sim]:
    """Best feasible ordering of `acts` within the window, or None."""
    if not acts:
        return _simulate(w, [], request, hotel_pt, tz_name)
    best: Optional[_Sim] = None
    for order in permutations(acts):
        sim = _simulate(w, order, request, hotel_pt, tz_name)
        if sim and (best is None or sim.cost < best.cost):
            best = sim
    return best


# ---------------------------------------------------------------------------
# Multi-day assembly
# ---------------------------------------------------------------------------


def _area_label(acts: List[Activity]) -> Optional[str]:
    pts = [_pt(a) for a in acts if a.has_coordinates]
    c = centroid(pts)
    if c is None:
        return None
    central = min((a for a in acts if a.has_coordinates), key=lambda a: haversine_km(c, _pt(a)))
    return f"Around {central.address or central.name}"


def _transport_items(w: DayWindow, request: ItineraryRequest, tz_name) -> List[ScheduledItem]:
    out = []
    t = request.transport
    note = "Confirmed transport." if t.is_confirmed else "Provisional: transport not yet selected by the user."
    if w.arrival:
        out.append(ScheduledItem(
            item_id=f"d{w.day_number}-arr", kind=ItemKind.ARRIVAL,
            title=f"Arrive at {t.arrival_location or request.destination.name}",
            start=w.arrival, end=w.arrival + timedelta(minutes=ARRIVAL_BUFFER_MIN), timezone=tz_name,
            notes=[note, f"{ARRIVAL_BUFFER_MIN} min estimated buffer for baggage and transfer."],
        ))
    if w.departure:
        out.append(ScheduledItem(
            item_id=f"d{w.day_number}-dep", kind=ItemKind.DEPARTURE,
            title=f"Leave for {t.departure_location or 'departure'}",
            start=w.departure - timedelta(minutes=DEPARTURE_BUFFER_MIN), end=w.departure, timezone=tz_name,
            notes=[note, f"{DEPARTURE_BUFFER_MIN} min estimated buffer for transfer and check-in."],
        ))
    return out


def build_schedule(
    request: ItineraryRequest,
    ranked: List[Activity],
    windows: List[DayWindow],
    budget_remaining: Optional[Decimal] = None,
    exclude_ids: Optional[Set[str]] = None,
) -> Tuple[List[DayPlan], List[Activity], List[Activity], List[str]]:
    """Return (day_plans, scheduled_activities, unscheduled_candidates, notes)."""
    hotel_pt = (request.hotel.latitude, request.hotel.longitude) if (
        request.hotel.latitude is not None and request.hotel.longitude is not None) else None
    tz_name = request.destination.timezone if resolve_tz(request.destination.timezone) else None
    travellers = request.travellers.total
    used: Set[str] = set(exclude_ids or ())
    notes: List[str] = []
    if hotel_pt is None:
        notes.append("Hotel location unknown: travel time to the first activity of each day is not estimated.")

    plans: Dict[int, DayPlan] = {}
    scheduled: List[Activity] = []

    def affordable(a: Activity) -> bool:
        if budget_remaining is None:
            return True
        c = activity_cost(a, travellers, request.currency)
        return c is None or c <= budget_remaining

    # Best days (most capacity) pick first, so long activities land on full days.
    order = sorted(windows, key=lambda w: (-w.capacity, w.day_number))
    for w in order:
        chosen: List[Activity] = []
        sim = None
        if w.capacity > 0:
            tried: Set[str] = set()
            while len(chosen) < w.capacity:
                pool = [a for a in ranked if a.activity_id not in used and a.activity_id not in tried and affordable(a)]
                if not pool:
                    break
                c = centroid([_pt(a) for a in chosen if a.has_coordinates])

                def key(a: Activity):
                    s = a.relevance_score or 0.0
                    if c is not None:
                        s -= (DISTANCE_PENALTY_PER_KM * haversine_km(c, _pt(a))) if a.has_coordinates else NO_COORDS_PENALTY
                    return (-s, a.activity_id)

                accepted = False
                for cand in sorted(pool, key=key)[:MAX_CANDIDATES_PER_SLOT]:
                    tried.add(cand.activity_id)
                    trial = schedule_day(w, chosen + [cand], request, hotel_pt, tz_name)
                    if trial is not None:
                        chosen.append(cand)
                        sim = trial
                        used.add(cand.activity_id)
                        if budget_remaining is not None:
                            budget_remaining -= activity_cost(cand, travellers, request.currency) or Decimal("0")
                        accepted = True
                        break
                if not accepted:
                    break
            if sim is None:
                sim = schedule_day(w, [], request, hotel_pt, tz_name)

        items = (sim.items if sim else []) + _transport_items(w, request, tz_name)
        items.sort(key=lambda it: it.start)
        day_cost = sum((it.estimated_cost or Decimal("0")) for it in items)
        day_notes = list(w.notes)
        if w.capacity > 0 and not chosen:
            day_notes.append("No suitable activity fitted this day's constraints.")
        plans[w.day_number] = DayPlan(
            day_number=w.day_number, date=w.date, day_type=w.day_type,
            area_label=_area_label(chosen), available_from=w.start, available_until=w.end,
            items=items, estimated_cost=day_cost,
            is_provisional=not (request.transport.is_confirmed and request.hotel.is_confirmed),
            notes=day_notes,
        )
        scheduled.extend(chosen)

    unscheduled = [a for a in ranked if a.activity_id not in used]
    missed_musts = [a.name for a in unscheduled if is_must_include(a, request.must_include)]
    if missed_musts:
        notes.append("Could not fit must-include activities: " + "; ".join(missed_musts))
    return [plans[k] for k in sorted(plans)], scheduled, unscheduled, notes
