"""Mechanical itinerary validation (TDD 4.4, 7.5).

Application code - not the LLM - decides whether a schedule is internally feasible.
Checks: overlaps, travel buffers, trip boundaries, arrival/departure, duplicates,
opening hours, date-specific availability, budget, and data-quality flags.
"""
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from app.agents.itinerary.calculations.scheduling import at, resolve_tz
from app.agents.itinerary.schemas import (
    Activity,
    AvailabilityStatus,
    DayPlan,
    EvidenceStatus,
    ItemKind,
    ItineraryRequest,
    PriceBasis,
    Severity,
    ValidationIssue,
)


def validate_itinerary(
    days: List[DayPlan], activities: List[Activity], request: ItineraryRequest, budget_spent: Decimal
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    by_id: Dict[str, Activity] = {a.activity_id: a for a in activities}
    tz = resolve_tz(request.destination.timezone)
    seen: Dict[str, int] = {}

    def issue(sev, code, msg, day=None, item=None):
        issues.append(ValidationIssue(severity=sev, code=code, message=msg, day_number=day, item_id=item))

    for day in days:
        if not (request.start_date <= day.date <= request.end_date):
            issue(Severity.ERROR, "outside_trip_dates", f"Day {day.day_number} ({day.date}) is outside the trip dates.", day.day_number)

        timed = [it for it in day.items if it.kind not in (ItemKind.ARRIVAL, ItemKind.DEPARTURE)]
        for prev, cur in zip(timed, timed[1:]):
            if cur.start < prev.end:
                issue(Severity.ERROR, "overlap", f"'{cur.title}' overlaps '{prev.title}'.", day.day_number, cur.item_id)
            elif cur.kind == ItemKind.ACTIVITY and cur.travel_from_previous:
                gap = (cur.start - prev.end).total_seconds() / 60
                if gap + 1e-6 < cur.travel_from_previous.minutes:
                    issue(Severity.ERROR, "insufficient_travel_buffer",
                          f"Only {int(gap)} min before '{cur.title}' but ~{cur.travel_from_previous.minutes} min travel is estimated.",
                          day.day_number, cur.item_id)

        for it in day.items:
            if it.end <= it.start:
                issue(Severity.ERROR, "invalid_time_block", f"'{it.title}' ends before it starts.", day.day_number, it.item_id)
            if it.kind != ItemKind.ACTIVITY:
                continue
            if day.available_from and it.start < day.available_from:
                issue(Severity.ERROR, "before_available_time",
                      f"'{it.title}' starts before the traveller is available (arrival buffer / day start).", day.day_number, it.item_id)
            if day.available_until and it.end > day.available_until:
                issue(Severity.ERROR, "after_available_time",
                      f"'{it.title}' ends after the traveller must leave / day ends.", day.day_number, it.item_id)

            a = by_id.get(it.activity_id or "")
            if a is None:
                issue(Severity.ERROR, "unknown_activity", f"'{it.title}' has no matching activity record.", day.day_number, it.item_id)
                continue

            if a.activity_id in seen:
                issue(Severity.ERROR, "duplicate_activity",
                      f"'{a.name}' is scheduled on day {seen[a.activity_id]} and day {day.day_number}.", day.day_number, it.item_id)
            seen.setdefault(a.activity_id, day.day_number)

            oh = a.opening_hours
            if oh.open_time and oh.close_time:
                o, c = at(day.date, oh.open_time, tz), at(day.date, oh.close_time, tz)
                if c <= o:
                    c += timedelta(days=1)
                if it.start < o or it.end > c:
                    issue(Severity.ERROR, "opening_hours_conflict",
                          f"'{a.name}' is scheduled outside its listed hours {oh.open_time:%H:%M}-{oh.close_time:%H:%M}.",
                          day.day_number, it.item_id)
                elif oh.status != EvidenceStatus.VERIFIED:
                    issue(Severity.INFO, "opening_hours_not_date_specific",
                          f"Hours for '{a.name}' are general, not confirmed for {day.date}.", day.day_number, it.item_id)
            else:
                issue(Severity.WARNING, "opening_hours_unknown",
                      f"Opening hours for '{a.name}' are unknown - verify before visiting.", day.day_number, it.item_id)

            if a.available_dates is not None and day.date not in a.available_dates:
                issue(Severity.ERROR, "not_available_on_date",
                      f"Provider shows no availability for '{a.name}' on {day.date}.", day.day_number, it.item_id)
            elif a.availability_status == AvailabilityStatus.UNKNOWN:
                issue(Severity.INFO, "availability_unchecked",
                      f"Availability for '{a.name}' on {day.date} has not been checked.", day.day_number, it.item_id)

            if a.price is None:
                issue(Severity.WARNING, "price_unknown", f"No price available for '{a.name}'.", day.day_number, it.item_id)
            elif a.price_basis == PriceBasis.UNKNOWN:
                issue(Severity.INFO, "price_basis_unknown",
                      f"Price basis for '{a.name}' unknown; costed per person.", day.day_number, it.item_id)
            if a.currency and a.currency.upper() != request.currency.upper():
                issue(Severity.WARNING, "currency_mismatch",
                      f"'{a.name}' is priced in {a.currency}, not {request.currency}; excluded from the total.", day.day_number, it.item_id)
            if "accessibility_unverified" in a.confidence_flags:
                issue(Severity.WARNING, "accessibility_unverified",
                      f"Accessibility of '{a.name}' is not confirmed by the provider.", day.day_number, it.item_id)
            if it.travel_from_previous and it.travel_from_previous.mode == "unknown":
                issue(Severity.WARNING, "travel_time_unknown",
                      f"Travel time to '{a.name}' could not be estimated (missing coordinates); 30 min assumed.", day.day_number, it.item_id)

    if request.budget.max_total is not None and budget_spent > request.budget.max_total:
        issue(Severity.WARNING, "budget_exceeded",
              f"Estimated activity cost {budget_spent} {request.currency} exceeds the activity budget {request.budget.max_total}.")

    if any(a.is_ai_suggested for a in activities):
        issue(Severity.WARNING, "ai_suggestions",
              "Activities are AI suggestions from Gemini: names, hours, prices and locations are estimates. Check them before you go.")
    if any(a.is_demo_data for a in activities):
        issue(Severity.WARNING, "demo_data", "Itinerary uses offline DEMO data, not live provider inventory.")
    if not request.transport.is_confirmed:
        issue(Severity.INFO, "transport_not_confirmed", "Transport is not confirmed; arrival/departure days are provisional.")
    if not request.hotel.is_confirmed:
        issue(Severity.INFO, "hotel_not_confirmed", "Hotel is not confirmed; daily start points and travel times are provisional.")

    return issues
