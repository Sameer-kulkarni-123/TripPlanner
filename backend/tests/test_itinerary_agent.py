from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional

import httpx
import pytest

from app.agents.itinerary.agent import ItineraryAgent, request_from_trip_state
from app.agents.itinerary.calculations.filtering import filter_activities, score_activities
from app.agents.itinerary.calculations.geo import estimate_travel, haversine_km
from app.agents.itinerary.calculations.scheduling import compute_day_windows
from app.agents.itinerary.providers.base import BaseExperienceProvider, ProviderSearchResult
from app.agents.itinerary.providers.experiences_nuitee import NuiteeExperienceProvider
from app.agents.itinerary.schemas import (
    Activity,
    DayType,
    EvidenceStatus,
    ItemKind,
    ItineraryRequest,
    OpeningHours,
    PlanStatus,
    PriceBasis,
    RevisionRequest,
)
from app.agents.itinerary.services.planner import ItineraryPlanner

ROME = (41.8967, 12.4822)


def make_activity(i: int, name: str, cats: List[str], dn_km: float = 0.0, de_km: float = 0.0, dur: int = 120,
                  price: Optional[str] = "20", open_t=time(9, 0), close_t=time(18, 0), **kw) -> Activity:
    return Activity(
        activity_id=f"t-{i}", provider_activity_id=str(i), provider_name="Mock", name=name, category=cats[0],
        categories=cats, latitude=ROME[0] + dn_km / 111.0, longitude=ROME[1] + de_km / 83.0,
        duration_minutes=dur, opening_hours=OpeningHours(open_time=open_t, close_time=close_t,
                                                         status=EvidenceStatus.INDICATIVE if open_t else EvidenceStatus.UNKNOWN),
        price=Decimal(price) if price is not None else None, currency="EUR", price_basis=PriceBasis.PER_PERSON,
        rating=4.5, rating_count=200, **kw,
    )


CATALOGUE = [
    make_activity(1, "Colosseum guided tour", ["History", "Sightseeing"], 0.5, 0.5, 180, "45"),
    make_activity(2, "Vatican Museums", ["Museums", "Art", "History"], 1.0, -3.0, 180, "35", time(8, 0), time(18, 0)),
    make_activity(3, "Trastevere food tour", ["Food & Drink"], -0.8, -0.9, 180, "70", time(11, 0), time(22, 0)),
    make_activity(4, "Borghese Gallery", ["Art", "Museums"], 2.0, 0.6, 120, "25"),
    make_activity(5, "Pantheon visit", ["History", "Architecture"], 0.2, -0.4, 60, "5"),
    make_activity(6, "Pub crawl", ["Nightlife"], -0.2, 0.1, 180, "30", time(20, 0), time(23, 59)),
    make_activity(7, "Catacombs tour", ["History"], -4.0, 2.0, 150, "20", wheelchair_accessible=False),
    make_activity(8, "Pasta making class", ["Food & Drink", "Workshops"], 0.1, 0.2, 180, "80", time(10, 0), time(17, 0)),
    make_activity(9, "Gelato walk", ["Food & Drink"], 0.3, -0.2, 90, None, None, None),
    make_activity(10, "Tivoli day trip", ["Day Trips", "History"], 25.0, 20.0, 480, "90", time(8, 0), time(19, 0)),
]


class MockProvider(BaseExperienceProvider):
    def __init__(self, acts=None):
        self.acts = acts if acts is not None else CATALOGUE

    @property
    def name(self):
        return "Mock"

    async def is_available(self):
        return True

    async def search(self, request):
        return ProviderSearchResult(activities=[a.model_copy(deep=True) for a in self.acts])


def base_request(**over) -> dict:
    req = {
        "destination": {"name": "Rome", "latitude": ROME[0], "longitude": ROME[1], "timezone": "Europe/Rome"},
        "start_date": "2026-11-20", "end_date": "2026-11-23",
        "travellers": {"adults": 2},
        "interests": ["history", "food", "art"],
        "currency": "EUR",
        "transport": {"arrival_datetime": "2026-11-20T11:30:00", "departure_datetime": "2026-11-23T18:00:00"},
        "hotel": {"name": "Hotel", "latitude": ROME[0] + 0.001, "longitude": ROME[1] - 0.004},
    }
    req.update(over)
    return req


def planner():
    return ItineraryPlanner(providers=[MockProvider()], demo_fallback=False)


# --------------------------------------------------------------------------- calculations

def test_haversine_and_travel_estimates():
    assert haversine_km((41.9, 12.5), (41.9, 12.5)) == 0
    assert 110 < haversine_km((0, 0), (1, 0)) < 112
    assert estimate_travel(None, (1, 1))[2] == "unknown"
    _, mins, mode = estimate_travel(ROME, (ROME[0] + 0.005, ROME[1]))
    assert mode == "walk" and mins >= 5
    _, mins, mode = estimate_travel(ROME, (ROME[0] + 0.05, ROME[1]))
    assert mode == "transit" and mins > 20


def test_day_windows_apply_arrival_and_departure_buffers():
    windows, assumptions = compute_day_windows(ItineraryRequest(**base_request()))
    assert [w.day_type for w in windows] == [DayType.ARRIVAL, DayType.FULL, DayType.FULL, DayType.DEPARTURE]
    assert windows[0].start.hour == 13 and windows[0].start.minute == 30   # 11:30 + 120
    assert windows[-1].end.hour == 15                                     # 18:00 - 180
    assert windows[0].start.tzinfo is not None
    assert any("provisional" in a for a in assumptions)


def test_days_before_arrival_get_no_activities():
    req = ItineraryRequest(**base_request(transport={"arrival_datetime": "2026-11-21T22:00:00"}))
    windows, _ = compute_day_windows(req)
    assert windows[0].capacity == 0 and windows[1].capacity == 0
    assert windows[2].capacity > 0


def test_filtering_hard_constraints():
    req = ItineraryRequest(**base_request(
        avoid=["nightlife"], travellers={"adults": 1, "accessibility_needs": ["wheelchair"]},
        budget={"max_per_activity": 60}, max_activity_duration_minutes=300,
    ))
    kept, excluded = filter_activities([a.model_copy(deep=True) for a in CATALOGUE], req)
    reasons = {a.name: r for a, r in excluded}
    assert "Pub crawl" in reasons
    assert reasons["Catacombs tour"] == "not wheelchair accessible"
    assert "Trastevere food tour" in reasons and "Pasta making class" in reasons  # > 60
    assert "Tivoli day trip" in reasons                                             # > 300 min
    assert all("accessibility_unverified" in a.confidence_flags for a in kept)


def test_scoring_prefers_interest_matches():
    req = ItineraryRequest(**base_request(interests=["art"]))
    kept, _ = filter_activities([a.model_copy(deep=True) for a in CATALOGUE], req)
    ranked = score_activities(kept, req)
    assert ranked[0].name in {"Borghese Gallery", "Vatican Museums"}


# --------------------------------------------------------------------------- full plan

@pytest.mark.asyncio
async def test_plan_is_feasible_and_has_no_errors():
    res = await planner().plan(ItineraryRequest(**base_request()))
    assert res.plan_status == PlanStatus.PROVISIONAL       # transport/hotel unconfirmed
    assert len(res.days) == 4
    assert not [i for i in res.validation_issues if i.severity == "error"], res.validation_issues

    ids = [it.activity_id for d in res.days for it in d.items if it.kind == ItemKind.ACTIVITY]
    assert len(ids) == len(set(ids)) > 0                   # no duplicates
    for d in res.days:
        acts = [it for it in d.items if it.kind == ItemKind.ACTIVITY]
        for it in acts:
            assert d.available_from <= it.start and it.end <= d.available_until
        timed = [it for it in d.items if it.kind not in (ItemKind.ARRIVAL, ItemKind.DEPARTURE)]
        for a, b in zip(timed, timed[1:]):
            assert b.start >= a.end
    # arrival day has an arrival block, last day a departure block
    assert any(it.kind == ItemKind.ARRIVAL for it in res.days[0].items)
    assert any(it.kind == ItemKind.DEPARTURE for it in res.days[-1].items)
    # full days get a lunch break
    assert any(it.kind == ItemKind.MEAL and it.title == "Lunch break" for it in res.days[1].items)


@pytest.mark.asyncio
async def test_budget_is_respected():
    res = await planner().plan(ItineraryRequest(**base_request(budget={"max_total": 150})))
    assert res.cost_summary.total_estimated <= Decimal("150")
    assert res.cost_summary.within_budget is True


@pytest.mark.asyncio
async def test_opening_hours_are_respected():
    res = await planner().plan(ItineraryRequest(**base_request()))
    by_id = {a.activity_id: a for a in res.activities}
    for d in res.days:
        for it in d.items:
            if it.kind != ItemKind.ACTIVITY:
                continue
            oh = by_id[it.activity_id].opening_hours
            if oh.open_time:
                assert it.start.time() >= oh.open_time and it.end.time() <= oh.close_time


@pytest.mark.asyncio
async def test_validated_only_when_confirmed_and_no_errors():
    req = base_request()
    req["transport"]["is_confirmed"] = True
    req["hotel"]["is_confirmed"] = True
    res = await planner().plan(ItineraryRequest(**req))
    assert res.plan_status == PlanStatus.VALIDATED
    assert all(not d.is_provisional for d in res.days)


@pytest.mark.asyncio
async def test_unknown_hours_are_flagged_not_invented():
    only_gelato = [a for a in CATALOGUE if a.name == "Gelato walk"]
    p = ItineraryPlanner(providers=[MockProvider(only_gelato)], demo_fallback=False)
    res = await p.plan(ItineraryRequest(**base_request(interests=["food"])))
    codes = {i.code for i in res.validation_issues}
    assert "opening_hours_unknown" in codes and "price_unknown" in codes
    assert res.cost_summary.unpriced_activities == 1


@pytest.mark.asyncio
async def test_no_provider_and_no_demo_fails_cleanly():
    p = ItineraryPlanner(providers=[], demo_fallback=False)
    res = await p.plan(ItineraryRequest(**base_request()))
    assert res.plan_status == PlanStatus.FAILED
    assert res.limitations


@pytest.mark.asyncio
async def test_demo_mode_is_flagged():
    p = ItineraryPlanner(providers=[], demo_fallback=True)
    res = await p.plan(ItineraryRequest(**base_request()))
    assert res.plan_status == PlanStatus.PROVISIONAL
    assert any(i.code == "demo_data" for i in res.validation_issues)
    assert all(a.is_demo_data for a in res.activities)


# --------------------------------------------------------------------------- revision

@pytest.mark.asyncio
async def test_revision_only_touches_affected_days():
    p = planner()
    old_req = ItineraryRequest(**base_request())
    first = await p.plan(old_req)
    new_raw = base_request()
    new_raw["transport"]["arrival_datetime"] = "2026-11-20T17:00:00"
    new_req = ItineraryRequest(**new_raw)

    rev = await p.revise(RevisionRequest(previous=first, request=new_req, previous_request=old_req))
    assert rev.revised_days == [1]
    for n in (2, 3, 4):
        assert rev.days[n - 1].items == first.days[n - 1].items
    assert rev.days[0].available_from.hour == 19
    ids = [it.activity_id for d in rev.days for it in d.items if it.activity_id]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_revision_full_rebuild_when_preferences_change():
    p = planner()
    old_req = ItineraryRequest(**base_request())
    first = await p.plan(old_req)
    new_req = ItineraryRequest(**base_request(interests=["art"]))
    rev = await p.revise(RevisionRequest(previous=first, request=new_req, previous_request=old_req))
    assert rev.revised_days == [1, 2, 3, 4]


# --------------------------------------------------------------------------- Nuitee adapter

NUITEE_PAYLOAD = {"data": {"meta": {"totalCount": 2, "limit": 50, "offset": 0}, "tours": [
    {"id": 903304, "title": "Skip-the-line Colosseum", "overallRating": 4.7, "numberOfRatings": 1523,
     "price": {"amount": 45.5, "currency": "EUR"}, "priceDescription": "per person",
     "durations": [{"value": 2, "unit": "hours"}], "openingHours": {"from": "08:30", "to": "19:00"},
     "categories": [{"id": 12, "name": "Sightseeing"}], "coordinates": {"lat": 41.8902, "long": 12.4922},
     "locations": [{"name": "Colosseum", "city": "Rome", "country": "IT"}],
     "notSuitableFor": "Wheelchair users", "cancellationPolicy": {"cancellable": True},
     "sourceUrl": "https://example.com/tour/903304"},
    {"id": 1, "title": "Mystery tour"},
]}}


def test_nuitee_query_params_and_parsing():
    prov = NuiteeExperienceProvider(api_key="k", base_url="https://api.liteapi.travel/v3.0")
    req = ItineraryRequest(**base_request(travellers={"adults": 1, "accessibility_needs": ["wheelchair"]},
                                          budget={"max_per_activity": 100}))
    params = dict(prov.build_query_params(req))
    assert params["location[latitude]"] == ROME[0] and "textSearch" not in params
    assert params["dateRange[from]"] == "2026-11-20" and params["flags"] == "wheelchair"
    assert params["price[max]"] == 100.0

    acts = prov.parse_tours(NUITEE_PAYLOAD, req)
    a, b = acts
    assert a.activity_id == "nuitee-exp-903304" and a.duration_minutes == 120
    assert a.price == Decimal("45.5") and a.price_basis == PriceBasis.PER_PERSON
    assert a.opening_hours.open_time == time(8, 30) and a.wheelchair_accessible is False
    assert a.address == "Colosseum, Rome, IT"
    assert b.duration_minutes == 120 and b.duration_status == EvidenceStatus.ESTIMATED
    assert {"price_unknown", "opening_hours_unknown", "coordinates_missing"} <= set(b.confidence_flags)


def test_nuitee_text_search_without_coordinates():
    prov = NuiteeExperienceProvider(api_key="k")
    req = ItineraryRequest(**base_request(destination={"name": "Rome"}))
    params = dict(prov.build_query_params(req))
    assert params["textSearch"] == "Rome" and "location[latitude]" not in params


@pytest.mark.asyncio
async def test_nuitee_search_handles_403(monkeypatch):
    async def fake_get(self, url, params=None, headers=None):
        return httpx.Response(403, json={"error": {"code": 403}}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    res = await NuiteeExperienceProvider(api_key="k").search(ItineraryRequest(**base_request()))
    assert res.activities == [] and "not enabled" in res.limitations[0]


@pytest.mark.asyncio
async def test_nuitee_search_success(monkeypatch):
    async def fake_get(self, url, params=None, headers=None):
        assert headers["X-API-Key"] == "k" and url.endswith("/experiences/tours")
        return httpx.Response(200, json=NUITEE_PAYLOAD, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    res = await NuiteeExperienceProvider(api_key="k").search(ItineraryRequest(**base_request()))
    assert len(res.activities) == 2


# --------------------------------------------------------------------------- agent / orchestrator glue

@pytest.mark.asyncio
async def test_agent_execute_and_state_mapping():
    agent = ItineraryAgent(planner=planner())
    out = await agent.execute(base_request())
    assert out["status"] == "success" and out["itinerary"]["days"]

    bad = await agent.execute({"destination": {"name": "Rome"}, "start_date": "2026-11-23", "end_date": "2026-11-20"})
    assert bad["status"] == "error" and bad["errors"]

    state = {
        "destination": {"name": "Rome", "latitude": ROME[0], "longitude": ROME[1], "timezone": "Europe/Rome"},
        "date_constraints": {"start_date": "2026-11-20", "end_date": "2026-11-22"},
        "traveller_details": {"adults": 2},
        "budget": {"currency": "EUR", "activities_max": 300},
        "preferences": {"interests": ["history"], "pace": "relaxed"},
        "transport_options": [{"option_id": "f1", "arrival_time": "2026-11-20T10:00:00+00:00", "destination_name": "FCO"}],
        "agent_status": {"travel": "success"},
    }
    req = request_from_trip_state(state)
    assert req.transport.is_confirmed is False and req.transport.arrival_datetime is not None
    update = await agent.execute_from_state(state)
    assert update["agent_status"]["itinerary"] == "provisional"
    assert update["agent_status"]["travel"] == "success"
    assert update["itinerary"]["days"]
