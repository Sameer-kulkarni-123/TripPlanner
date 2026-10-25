"""Gemini client, AI activity suggestions, place search and trip-draft extraction (all network mocked)."""
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents.itinerary.providers.base import BaseExperienceProvider, ProviderSearchResult
from app.agents.itinerary.providers.experiences_gemini import GeminiExperienceProvider
from app.agents.itinerary.schemas import ItineraryRequest, Severity
from app.agents.itinerary.services.planner import ItineraryPlanner
from app.core.config import settings
from app.integrations import gemini, places

MYSURU = (12.2958, 76.6394)


def mysuru_request(**over) -> ItineraryRequest:
    start = date.today() + timedelta(days=40)
    req = {
        "destination": {"name": "Mysuru", "country_code": "IN", "latitude": MYSURU[0], "longitude": MYSURU[1],
                        "timezone": "Asia/Kolkata"},
        "start_date": start.isoformat(), "end_date": (start + timedelta(days=2)).isoformat(),
        "travellers": {"adults": 2}, "interests": ["history", "food"], "currency": "INR",
    }
    req.update(over)
    return ItineraryRequest(**req)


GEMINI_ITEMS = [
    {"name": "Mysore Palace", "category": "history", "categories": ["history", "architecture"],
     "description": "Royal palace of the Wadiyar dynasty.", "address": "Sayyaji Rao Rd",
     "latitude": 12.3052, "longitude": 76.6552, "duration_minutes": 120, "opening_time": "10:00",
     "closing_time": "17:30", "price_per_person": 120, "wheelchair_accessible": None, "min_age": None},
    {"name": "Devaraja Market", "category": "food", "categories": ["food", "shopping"], "description": "Old market.",
     "latitude": 12.3100, "longitude": 76.6520, "duration_minutes": 60, "opening_time": None, "closing_time": None,
     "price_per_person": 0},
    {"name": "Somewhere far away", "category": "nature", "latitude": 19.07, "longitude": 72.87, "duration_minutes": 90},
    {"name": "", "duration_minutes": 60},
    {"name": "No duration", "latitude": 12.3, "longitude": 76.6},
]


# ------------------------------------------------------------------ gemini client
@pytest.mark.asyncio
async def test_gemini_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    with pytest.raises(gemini.GeminiError, match="GEMINI_API_KEY"):
        await gemini.generate_json("hi")


@pytest.mark.asyncio
async def test_gemini_falls_back_to_next_model_and_parses_fenced_json(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini, "_auth_mode", None)
    monkeypatch.setattr(settings, "GEMINI_MODEL", "missing-model")
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODELS", "good-model")
    calls = []

    async def fake_post(self, url, json=None, headers=None, params=None, **kw):
        calls.append(url)
        assert headers["x-goog-api-key"] == "test-key"
        if "missing-model" in url:
            return httpx.Response(404, json={})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '```json\n{"ok": true}\n```'}]}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await gemini.generate_json("hi") == {"ok": True}
    assert len(calls) == 2 and "good-model:generateContent" in calls[1]


@pytest.mark.asyncio
async def test_gemini_bad_key_is_explained(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "bad")
    monkeypatch.setattr(gemini, "_auth_mode", None)

    async def fake_post(self, url, json=None, headers=None, params=None, **kw):
        return httpx.Response(403, json={})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(gemini.GeminiError, match="rejected the API key"):
        await gemini.generate_json("hi")


# ------------------------------------------------------------------ AI activity suggestions
def test_gemini_suggestions_are_validated_and_flagged():
    res = GeminiExperienceProvider().parse(GEMINI_ITEMS, mysuru_request())
    names = [a.name for a in res.activities]
    assert names == ["Mysore Palace", "Devaraja Market"]          # far-away and malformed items dropped
    palace, market = res.activities
    assert palace.is_ai_suggested and not palace.is_demo_data
    assert palace.price_status.value == "estimated" and palace.opening_hours.status.value == "estimated"
    assert "coordinates_estimated" in palace.confidence_flags
    assert market.opening_hours.open_time is None and "opening_hours_unknown" in market.confidence_flags
    assert any("more than" in l for l in res.limitations)
    assert any("required fields" in l for l in res.limitations)


class FakeAI(BaseExperienceProvider):
    @property
    def name(self):
        return "Gemini (AI suggestions)"

    async def is_available(self):
        return True

    async def search(self, request):
        return GeminiExperienceProvider().parse(GEMINI_ITEMS, request)


class EmptyLive(BaseExperienceProvider):
    @property
    def name(self):
        return "Nuitee/LiteAPI Experiences"

    async def is_available(self):
        return True

    async def search(self, request):
        return ProviderSearchResult(limitations=["Nuitee Experiences access is not enabled for this API key (HTTP 403)."])


@pytest.mark.asyncio
async def test_planner_uses_gemini_before_demo_and_stays_provisional():
    planner = ItineraryPlanner(providers=[EmptyLive()], demo_fallback=True, ai_provider=FakeAI())
    req = mysuru_request(transport={"is_confirmed": True}, hotel={"is_confirmed": True, "latitude": 12.30, "longitude": 76.65})
    result = await planner.plan(req)
    assert result.activities and all(a.is_ai_suggested for a in result.activities)
    assert not any(a.is_demo_data for a in result.activities)
    assert result.plan_status.value == "provisional"               # an LLM is never the authority
    assert any(i.code == "ai_suggestions" and i.severity == Severity.WARNING for i in result.validation_issues)
    assert any("403" in l for l in result.limitations)


@pytest.mark.asyncio
async def test_planner_without_gemini_still_uses_demo():
    class Off(FakeAI):
        async def is_available(self):
            return False

    result = await ItineraryPlanner(providers=[EmptyLive()], demo_fallback=True, ai_provider=Off()).plan(mysuru_request())
    assert result.activities and all(a.is_demo_data for a in result.activities)


# ------------------------------------------------------------------ place search
@pytest.mark.asyncio
async def test_place_search_attaches_nearest_airport(monkeypatch):
    monkeypatch.setattr(places, "_airports", None)
    monkeypatch.setattr(settings, "NUITEE_API_KEY", "sand_test")

    async def fake_get(self, url, params=None, headers=None):
        if "geocoding" in url:
            return httpx.Response(200, json={"results": [
                {"name": "Mysuru", "latitude": 12.2958, "longitude": 76.6394, "country_code": "IN", "country": "India",
                 "admin1": "Karnataka", "timezone": "Asia/Kolkata", "feature_code": "PPLA2", "population": 920550},
            ]})
        assert url.endswith("/data/iataCodes")
        return httpx.Response(200, json={"data": [
            {"code": "MYQ", "name": "Mysore Airport", "latitude": 12.23, "longitude": 76.656, "countryCode": "IN"},
            {"code": "BLR", "name": "Kempegowda International", "latitude": 13.1986, "longitude": 77.7066, "countryCode": "IN"},
            {"code": "CMB", "name": "Colombo", "latitude": 7.18, "longitude": 79.88, "countryCode": "LK"},
        ]})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    res = await places.search_places("Mysuru")
    assert res[0]["city"] == "Mysuru" and res[0]["timezone"] == "Asia/Kolkata"
    assert res[0]["airport"]["code"] == "MYQ" and res[0]["airport"]["distance_km"] < 15
    monkeypatch.setattr(places, "_airports", None)


# ------------------------------------------------------------------ trip draft
def test_trip_draft_extracts_and_resolves(monkeypatch):
    from app.main import app
    from app.api import assistant

    start = date.today() + timedelta(days=20)

    async def fake_gen(prompt, **kw):
        assert "Mysuru" in prompt
        return {"destination": "Mysuru", "origin": "Bengaluru", "start_date": start.isoformat(), "end_date": None,
                "nights": 2, "adults": 2, "children_ages": [7, 30], "interests": ["history", "palaces"],
                "avoid": ["nightlife", "history"], "pace": "relaxed", "activity_budget": 3000, "currency": "INR",
                "wheelchair": False}

    async def fake_places(name, count=8, country_code=None, **kw):
        return [{"city": name, "country_code": "IN", "latitude": 12.0, "longitude": 76.0, "timezone": "Asia/Kolkata",
                 "airport": None}]

    monkeypatch.setattr(assistant.gemini, "generate_json", fake_gen)
    monkeypatch.setattr(assistant, "search_places", fake_places)
    r = TestClient(app).post("/api/v1/assistant/trip-draft", json={"text": "2 nights in Mysuru from Bengaluru, relaxed"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["destination"]["city"] == "Mysuru" and d["origin"]["city"] == "Bengaluru"
    assert d["end_date"] == (start + timedelta(days=2)).isoformat()
    assert d["children_ages"] == [7]                       # out-of-range ages dropped
    assert d["interests"] == ["history"] and d["avoid"] == ["nightlife"]   # unknown / conflicting values dropped
    assert d["missing"] == []


def test_trip_draft_without_key_returns_503(monkeypatch):
    from app.main import app
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    r = TestClient(app).post("/api/v1/assistant/trip-draft", json={"text": "a weekend in Jaipur"})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


# ------------------------------------------------------------------ ranking, regions and airport choice
AIRPORTS = [
    {"code": "BPM", "name": "Begumpet Airport", "lat": 17.4531, "lon": 78.4676, "country": "IN"},
    {"code": "HYD", "name": "Rajiv Gandhi International Airport", "lat": 17.2403, "lon": 78.4294, "country": "IN"},
    {"code": "GOI", "name": "Goa International Airport", "lat": 15.3808, "lon": 73.8314, "country": "IN"},
    {"code": "IXG", "name": "Belagavi Airport", "lat": 15.8593, "lon": 74.6183, "country": "IN"},
    {"code": "WNP", "name": "Naga Airport", "lat": 13.5849, "lon": 123.2700, "country": "PH"},
    {"code": "MYQ", "name": "Mysore Airport", "lat": 12.23, "lon": 76.656, "country": "IN"},
]


def test_airport_prefers_international_over_closer_city_field():
    a = places.nearest_airport(17.385, 78.4867, "IN", AIRPORTS)        # Hyderabad centre: BPM is ~8 km, HYD ~22 km
    assert a["code"] == "HYD"
    assert places.nearest_airport(12.2958, 76.6394, "IN", AIRPORTS)["code"] == "MYQ"   # no international nearby
    assert places.nearest_airport(17.385, 78.4867, "IN", AIRPORTS, prefer_code="BPM")["code"] == "BPM"
    assert places.nearest_airport(17.385, 78.4867, "IN", AIRPORTS, prefer_code="XXX")["code"] == "HYD"


@pytest.mark.asyncio
async def test_goa_finds_the_indian_state_not_a_namesake(monkeypatch):
    monkeypatch.setattr(places, "_airports", AIRPORTS)

    async def fake_get(self, url, params=None, headers=None):
        return httpx.Response(200, json={"results": [
            {"name": "Goa", "latitude": 13.698, "longitude": 123.488, "country_code": "PH", "country": "Philippines",
             "admin1": "Bicol", "timezone": "Asia/Manila", "feature_code": "PPL", "population": 64000},
            {"name": "Goa", "latitude": 15.333, "longitude": 74.083, "country_code": "IN", "country": "India",
             "timezone": "Asia/Kolkata", "feature_code": "ADM1"},
            {"name": "Goa Velha", "latitude": 15.44, "longitude": 73.88, "country_code": "IN", "country": "India",
             "admin1": "Goa", "timezone": "Asia/Kolkata", "feature_code": "PPL", "population": 5000},
        ]})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    res = await places.search_places("goa", prefer="IN", use_ai=False)
    top = res[0]
    assert top["country_code"] == "IN" and top["kind"] == "region" and top["base"] == "Panaji"
    assert abs(top["latitude"] - 15.4989) < 0.01                       # tourist base, not the state's centre
    assert top["airport"]["code"] == "GOI"
    assert {r["country_code"] for r in res} == {"IN", "PH"}            # the namesake is still offered, lower down


@pytest.mark.asyncio
async def test_gemini_resolves_nicknames_but_only_keeps_real_places(monkeypatch):
    monkeypatch.setattr(places, "_airports", AIRPORTS)
    from app.integrations import gemini as gem

    async def fake_get(self, url, params=None, headers=None):
        if params["name"] == "Kodagu":
            return httpx.Response(200, json={"results": [
                {"name": "Kodagu", "latitude": 12.42, "longitude": 75.74, "country_code": "IN", "country": "India",
                 "admin1": "Karnataka", "timezone": "Asia/Kolkata", "feature_code": "ADM2"}]})
        if params["name"] == "Faraway Hills":
            return httpx.Response(200, json={"results": [
                {"name": "Faraway Hills", "latitude": 40.0, "longitude": -100.0, "country_code": "US",
                 "timezone": "America/Chicago", "feature_code": "PPL"}]})
        return httpx.Response(200, json={})                              # "coorg" and the invented place: nothing

    async def fake_gen(prompt, **kw):
        assert '"coorg"' in prompt and "IN" in prompt
        return {"candidates": [
            {"name": "Kodagu", "kind": "region", "country_code": "IN", "latitude": 12.42, "longitude": 75.74, "airport_iata": "MYQ"},
            {"name": "Faraway Hills", "kind": "city", "country_code": "IN", "latitude": 12.0, "longitude": 77.0},
            {"name": "Atlantis", "kind": "city", "country_code": "IN", "latitude": 12.0, "longitude": 77.0},
        ]}

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(gem, "is_configured", lambda: True)
    monkeypatch.setattr(gem, "generate_json", fake_gen)
    res = await places.search_places("coorg", prefer="IN")
    assert [r["city"] for r in res] == ["Kodagu"]                      # wrong-coordinates and invented ones dropped
    assert res[0]["kind"] == "region" and res[0]["base"] == "Madikeri"
    assert res[0]["airport"]["code"] == "MYQ" and "Gemini" in res[0]["source"]


@pytest.mark.asyncio
async def test_gemini_retries_other_auth_styles_on_401(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AQ.newstyle")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "m1")
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODELS", "")
    monkeypatch.setattr(gemini, "_auth_mode", None)
    seen = []

    async def fake_post(self, url, json=None, headers=None, params=None, **kw):
        mode = "query" if params else ("bearer" if "authorization" in headers else "header")
        seen.append(mode)
        if mode != "query":
            return httpx.Response(401, json={"error": {"status": "UNAUTHENTICATED"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": 1}'}]}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await gemini.generate_json("hi") == {"ok": 1}
    assert seen == ["header", "query"] and gemini._auth_mode == "query"
    monkeypatch.setattr(gemini, "_auth_mode", None)


@pytest.mark.asyncio
async def test_gemini_busy_model_is_retried_then_next_model_used(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "busy-model")
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODELS", "calm-model")
    monkeypatch.setattr(gemini, "_auth_mode", None)
    monkeypatch.setattr(gemini, "RETRY_DELAYS", (0, 0))
    calls = []

    async def fake_post(self, url, json=None, headers=None, params=None, **kw):
        calls.append(url)
        if "busy-model" in url:
            return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": 2}'}]}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await gemini.generate_json("hi") == {"ok": 2}
    assert sum("busy-model" in c for c in calls) == 3          # first try + 2 retries
    monkeypatch.setattr(gemini, "_auth_mode", None)


@pytest.mark.asyncio
async def test_gemini_all_models_busy_gives_clear_message(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "a")
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODELS", "b")
    monkeypatch.setattr(gemini, "_auth_mode", None)
    monkeypatch.setattr(gemini, "RETRY_DELAYS", (0,))

    async def fake_post(self, url, json=None, headers=None, params=None, **kw):
        return httpx.Response(503 if url.endswith("a:generateContent") else 429, json={})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(gemini.GeminiError, match="overloaded"):
        await gemini.generate_json("hi")
    monkeypatch.setattr(gemini, "_auth_mode", None)
