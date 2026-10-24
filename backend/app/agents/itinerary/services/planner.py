"""Itinerary planning service: discovery -> filter -> score -> schedule -> validate (TDD 7.4)."""
import asyncio
import logging
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional, Set, Tuple

from app.core.config import settings
from app.agents.itinerary.calculations.filtering import filter_activities, score_activities
from app.agents.itinerary.calculations.scheduling import (
    activity_cost,
    build_schedule,
    compute_day_windows,
    resolve_tz,
    to_local,
)
from app.agents.itinerary.calculations.validation import validate_itinerary
from app.agents.itinerary.providers.base import BaseExperienceProvider
from app.agents.itinerary.providers.demo import DemoExperienceProvider
from app.agents.itinerary.providers.experiences_nuitee import NuiteeExperienceProvider
from app.agents.itinerary.schemas import (
    Activity,
    ActivitySearchResult,
    CostSummary,
    DayPlan,
    ItemKind,
    ItineraryRequest,
    ItineraryResult,
    PlanStatus,
    RevisionRequest,
    Severity,
)

logger = logging.getLogger(__name__)

AVAILABILITY_CHECK_LIMIT = 15
AVAILABILITY_CONCURRENCY = 5
MAX_ALTERNATIVES = 10


class ItineraryPlanner:
    def __init__(self, providers: Optional[List[BaseExperienceProvider]] = None, demo_fallback: Optional[bool] = None):
        self.providers = providers if providers is not None else [NuiteeExperienceProvider()]
        self.demo_fallback = settings.ITINERARY_DEMO_MODE if demo_fallback is None else demo_fallback
        self.demo_provider = DemoExperienceProvider()

    # ------------------------------------------------------------------ discovery
    async def _active_providers(self) -> Tuple[List[BaseExperienceProvider], List[str]]:
        active = [p for p in self.providers if await p.is_available()]
        if active:
            return active, []
        if self.demo_fallback:
            return [self.demo_provider], []
        return [], ["No experience provider is configured (set NUITEE_API_KEY or enable ITINERARY_DEMO_MODE)."]

    async def discover(self, request: ItineraryRequest) -> Tuple[List[Activity], List[str]]:
        providers, limitations = await self._active_providers()
        results = await asyncio.gather(*(p.search(request) for p in providers), return_exceptions=True)
        activities: List[Activity] = []
        for p, r in zip(providers, results):
            if isinstance(r, Exception):
                logger.error(f"Provider {p.name} failed: {r}")
                limitations.append(f"{p.name} failed: {r}")
                continue
            activities.extend(r.activities)
            limitations.extend(r.limitations)

        # Fall back to demo data if live providers returned nothing at all.
        if not activities and self.demo_fallback and providers and not isinstance(providers[0], DemoExperienceProvider):
            demo = await self.demo_provider.search(request)
            activities, limitations = demo.activities, limitations + demo.limitations

        await self._enrich_availability(activities, request, providers)
        return activities, limitations

    async def _enrich_availability(self, activities: List[Activity], request: ItineraryRequest, providers) -> None:
        """Date-specific availability for the most promising candidates (bounded, concurrent)."""
        by_name = {p.name: p for p in providers}
        sem = asyncio.Semaphore(AVAILABILITY_CONCURRENCY)
        targets = [a for a in activities if a.provider_name in by_name][:AVAILABILITY_CHECK_LIMIT]

        async def check(a: Activity):
            async with sem:
                dates = await by_name[a.provider_name].get_available_dates(a.provider_activity_id, request.language)
            if dates is not None:
                a.available_dates = dates

        await asyncio.gather(*(check(a) for a in targets), return_exceptions=True)

    async def search_activities(self, request: ItineraryRequest) -> ActivitySearchResult:
        raw, limitations = await self.discover(request)
        kept, excluded = filter_activities(raw, request)
        ranked = score_activities(kept, request)
        return ActivitySearchResult(
            destination=request.destination.name, activities=ranked,
            excluded_count=len(excluded), limitations=limitations,
        )

    # ------------------------------------------------------------------ planning
    async def plan(self, request: ItineraryRequest) -> ItineraryResult:
        raw, limitations = await self.discover(request)
        return self.plan_from_activities(request, raw, limitations)

    def plan_from_activities(
        self,
        request: ItineraryRequest,
        raw: List[Activity],
        limitations: Optional[List[str]] = None,
        keep_days: Optional[List[DayPlan]] = None,
        keep_activities: Optional[List[Activity]] = None,
        revised_days: Optional[List[int]] = None,
    ) -> ItineraryResult:
        limitations = list(limitations or [])
        keep_days = keep_days or []
        keep_activities = keep_activities or []
        kept_ids: Set[str] = {a.activity_id for a in keep_activities}

        kept, excluded = filter_activities(raw, request)
        ranked = score_activities([a for a in kept if a.activity_id not in kept_ids], request)
        if excluded:
            reasons = {}
            for _, r in excluded:
                reasons[r] = reasons.get(r, 0) + 1
            limitations.append("Excluded by hard constraints: " + ", ".join(f"{n} {r}" for r, n in sorted(reasons.items())))

        windows, assumptions = compute_day_windows(request)
        keep_nums = {d.day_number for d in keep_days}
        windows = [w for w in windows if w.day_number not in keep_nums]

        spent_kept = sum((d.estimated_cost for d in keep_days), Decimal("0"))
        budget_left = None
        if request.budget.max_total is not None:
            budget_left = request.budget.max_total - spent_kept

        new_days, scheduled, unscheduled, notes = build_schedule(request, ranked, windows, budget_left, kept_ids)
        assumptions.extend(notes)
        if not request.hotel.is_confirmed:
            assumptions.append("Hotel not confirmed; the schedule is provisional.")

        days = sorted(keep_days + new_days, key=lambda d: d.day_number)
        used = keep_activities + scheduled
        total = sum((d.estimated_cost for d in days), Decimal("0"))
        travellers = request.travellers.total
        priced = sum(1 for a in used if activity_cost(a, travellers, request.currency) is not None)

        issues = validate_itinerary(days, used, request, total)
        has_errors = any(i.severity == Severity.ERROR for i in issues)
        n_activities = sum(1 for d in days for it in d.items if it.kind == ItemKind.ACTIVITY)
        if n_activities == 0:
            status = PlanStatus.FAILED
            limitations.append("No activities could be scheduled with the given constraints.")
        elif request.transport.is_confirmed and request.hotel.is_confirmed and not has_errors \
                and not any(a.is_demo_data for a in used):
            status = PlanStatus.VALIDATED
        else:
            status = PlanStatus.PROVISIONAL

        tz = resolve_tz(request.destination.timezone)
        return ItineraryResult(
            plan_status=status,
            destination=request.destination.name,
            start_date=request.start_date,
            end_date=request.end_date,
            timezone=request.destination.timezone if tz else None,
            days=days,
            activities=used,
            alternatives=unscheduled[:MAX_ALTERNATIVES],
            cost_summary=CostSummary(
                currency=request.currency,
                total_estimated=total,
                priced_activities=priced,
                unpriced_activities=len(used) - priced,
                budget_limit=request.budget.max_total,
                within_budget=None if request.budget.max_total is None else total <= request.budget.max_total,
            ),
            assumptions=assumptions,
            validation_issues=issues,
            limitations=limitations,
            revised_days=revised_days,
        )

    # ------------------------------------------------------------------ targeted revision (TDD 6.3, 7.7)
    @staticmethod
    def infer_affected_days(rev: RevisionRequest) -> Tuple[Optional[List[int]], List[str]]:
        """Return (day numbers to rebuild or None for all, reasons)."""
        new, old = rev.request, rev.previous_request
        if old is None:
            return None, ["No previous request supplied; rebuilding all days."]
        if (new.start_date, new.end_date, new.destination.name) != (old.start_date, old.end_date, old.destination.name):
            return None, ["Destination or trip dates changed; rebuilding all days."]
        for fld in ("interests", "avoid", "must_include", "pace", "travellers", "budget", "currency", "daily_window",
                    "max_activity_duration_minutes"):
            if getattr(new, fld) != getattr(old, fld):
                return None, [f"'{fld}' changed; rebuilding all days."]
        h_new, h_old = new.hotel, old.hotel
        if (h_new.latitude, h_new.longitude) != (h_old.latitude, h_old.longitude):
            return None, ["Hotel location changed; travel times for every day must be recalculated."]

        affected: Set[int] = set()
        reasons: List[str] = []
        tz = resolve_tz(new.destination.timezone)

        def day_no(dt):
            if dt is None:
                return None
            d = to_local(dt, tz).date()
            n = (d - new.start_date).days + 1
            return n if 1 <= n <= new.trip_days else None

        t_new, t_old = new.transport, old.transport
        if t_new.arrival_datetime != t_old.arrival_datetime:
            nums = {n for n in (day_no(t_new.arrival_datetime), day_no(t_old.arrival_datetime)) if n} or {1}
            # days before the new arrival are also affected
            first = day_no(t_new.arrival_datetime) or 1
            nums |= set(range(1, first + 1))
            affected |= nums
            reasons.append(f"Arrival time changed; revising day(s) {sorted(nums)}.")
        if t_new.departure_datetime != t_old.departure_datetime:
            last = day_no(t_new.departure_datetime) or new.trip_days
            nums = {n for n in (day_no(t_new.departure_datetime), day_no(t_old.departure_datetime)) if n} or {new.trip_days}
            nums |= set(range(last, new.trip_days + 1))
            affected |= nums
            reasons.append(f"Departure time changed; revising day(s) {sorted(nums)}.")
        if not affected:
            reasons.append("No schedule-relevant change detected; only confirmation status updated.")
        return sorted(affected), reasons

    async def revise(self, rev: RevisionRequest) -> ItineraryResult:
        if rev.days_to_revise is not None:
            days_to_revise, reasons = sorted(set(rev.days_to_revise)), [f"Revision requested for day(s) {sorted(set(rev.days_to_revise))}."]
        else:
            days_to_revise, reasons = self.infer_affected_days(rev)

        if days_to_revise is None:
            result = await self.plan(rev.request)
            result.revised_days = [d.day_number for d in result.days]
            result.assumptions = reasons + result.assumptions
            return result

        keep_days = [d for d in rev.previous.days if d.day_number not in days_to_revise]
        kept_activity_ids = {it.activity_id for d in keep_days for it in d.items if it.activity_id}
        keep_activities = [a for a in rev.previous.activities if a.activity_id in kept_activity_ids]
        # Re-flag kept days with the latest confirmation status.
        provisional = not (rev.request.transport.is_confirmed and rev.request.hotel.is_confirmed)
        for d in keep_days:
            d.is_provisional = provisional

        raw, limitations = await self.discover(rev.request)
        result = self.plan_from_activities(
            rev.request, raw, limitations,
            keep_days=keep_days, keep_activities=keep_activities, revised_days=days_to_revise,
        )
        result.assumptions = reasons + result.assumptions
        return result
