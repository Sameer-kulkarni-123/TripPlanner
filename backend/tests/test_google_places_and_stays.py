"""Google Places destination search and radius-based hotel search (all network mocked)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.agents.hotel.calculations.ranking import rank_hotel_options
from app.agents.hotel.providers.hotel_nuitee import NuiteeHotelProvider
from app.agents.hotel.schemas import HotelOption, HotelPreferences, HotelSearchRequest
from app.core.config import settings
from app.integrations import google_places as gpl
from app.integrations import places

LADAKH = {
    "id": "ChIJladakh", "displayName": {"text": "Ladakh"}, "formattedAddress": "Ladakh, India",
    "location": {"latitude": 34.2268, "longitude": 77.5619},
    "types": ["administrative_area_level_1", "political"],
    "addressComponents": [
        {"longText": "Ladakh", "shortText": "LA", "types": ["administrative_area_level_1", "political"]},
        {"longText": "India", "shortText": "IN", "types": ["country", "political"]},
    ],
}
PANGONG = {
    "id": "ChIJpangong", "displayName": {"text": "Pangong Lake"}, "formattedAddress": "Pangong Lake, Ladakh",
    "location": {"latitude": 33.7595, "longitude": 78.6674},
    "types": ["natural_feature", "tourist_attraction", "point_of_interest", "establishment"],
    "addressComponents": [
        {"longText": "Ladakh", "shortText": "LA", "types": ["administrative_area_level_1", "political"]},
        {"longText": "India", "shortText": "IN", "types": ["country", "political"]},
    ],
}
AIRPORTS = [
    {"code": "IXL", "name": "Kushok Bakula Rimpochee", "lat": 34.1359, "lon": 77.5465, "country": "IN"},
    {"code": "DEL", "name": "Indira Gandhi International", "lat": 28.5562, "lon": 77.1000, "country": "IN"},
]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    async def tz(lat, lon):
        return "Asia/Kolkata"

    async def airports():
        return AIRPORTS

    monkeypatch.setattr(gpl, "timezone_for", tz)
    monkeypatch.setattr(places, "_load_airports", airports)


def test_kind_and_generic_detection():
    assert gpl.kind_of(LADAKH["types"]) == "region"
    assert gpl.kind_of(PANGONG["types"]) == "landmark"
    assert gpl.kind_of(["locality", "political"]) == "city"
    assert gpl.is_generic_query("hill stations near Bengaluru")
    assert gpl.is_generic_query("beaches in goa")
    assert not gpl.is_generic_query("ladakh")


@pytest.mark.asyncio
async def test_ladakh_resolves_to_leh_base_with_ixl():
    p = await places._from_google(LADAKH, AIRPORTS)
    assert p["city"] == "Ladakh" and p["country_code"] == "IN"
    assert p["kind"] == "region" and p["base"] == "Leh"
    assert p["airport"]["code"] == "IXL"
    assert p["timezone"] == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_landmark_keeps_its_coordinates_and_finds_nearest_airport():
    p = await places._from_google(PANGONG, AIRPORTS)
    assert p["kind"] == "landmark" and p["region"] == "Ladakh"
    assert abs(p["latitude"] - 33.7595) < 1e-6
    assert p["airport"]["code"] == "IXL"


@pytest.mark.asyncio
async def test_suggest_uses_autocomplete_and_text_search_for_generic(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "k")
    calls = []

    async def fake_call(method, url, *, json=None, params=None, field_mask=None):
        calls.append(url.rsplit("/", 1)[-1])
        if url.endswith("places:autocomplete"):
            assert json["sessionToken"] == "s1"
            return {"suggestions": [
                {"placePrediction": {"placeId": "ChIJpangong", "types": PANGONG["types"],
                                     "structuredFormat": {"mainText": {"text": "Pangong Lake"},
                                                          "secondaryText": {"text": "Ladakh, India"}}}},
                {"placePrediction": {"placeId": "ChIJother", "types": ["locality"],
                                     "structuredFormat": {"mainText": {"text": "Leh"}}}},
            ]}
        if url.endswith("places:searchText"):
            assert "places.location" in field_mask
            return {"places": [PANGONG]}
        raise AssertionError(url)

    monkeypatch.setattr(gpl, "_call", fake_call)
    out = await places.suggest_places("lakes near leh", session="s1", prefer="IN")
    assert out["provider"] == "google"
    assert [r["city"] for r in out["results"]] == ["Pangong Lake"]
    # Pangong already resolved by text search, so it is not suggested twice
    assert [s["title"] for s in out["suggestions"]] == ["Leh"]
    assert calls == ["places:autocomplete", "places:searchText"]


@pytest.mark.asyncio
async def test_suggest_without_key_falls_back_to_open_meteo(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "")

    async def fake_search(q, count=8, country_code=None, prefer=None, use_ai=True):
        return [{"city": "Leh"}]

    monkeypatch.setattr(places, "search_places", fake_search)
    out = await places.suggest_places("leh")
    assert out == {"provider": "open-meteo", "suggestions": [], "results": [{"city": "Leh"}]}


@pytest.mark.asyncio
async def test_place_details_uses_session_and_pro_field(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "k")

    async def fake_call(method, url, *, json=None, params=None, field_mask=None):
        assert method == "GET" and url.endswith("/places/ChIJladakh")
        assert params["sessionToken"] == "s2" and "displayName" in field_mask
        return LADAKH

    monkeypatch.setattr(gpl, "_call", fake_call)
    p = await places.place_details("ChIJladakh", session="s2")
    assert p["base"] == "Leh"


# ------------------------------------------------------------------ hotels
def _req(**over):
    start = date.today() + timedelta(days=30)
    base = dict(destination="Ladakh", country_code="IN", check_in=start, check_out=start + timedelta(days=3))
    base.update(over)
    return HotelSearchRequest(**base)


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, ""

    def json(self):
        return self._data


class _Client:
    def __init__(self, pages):
        self.pages, self.params = pages, []

    async def get(self, url, params=None, headers=None):
        self.params.append(params)
        return _Resp({"data": self.pages.pop(0)})


@pytest.mark.asyncio
async def test_hotels_searched_by_radius_around_coordinates():
    prov = NuiteeHotelProvider(api_key="k", base_url="https://x", max_hotels=150)
    client = _Client([[{"id": "h1", "name": "Leh Guesthouse"}]])
    req = _req(latitude=34.15, longitude=77.58, radius_km=35)
    found = await prov._fetch_static_hotels(client, req)
    assert list(found) == ["h1"]
    p = client.params[0]
    assert p["latitude"] == 34.15 and p["radius"] == 35000 and "cityName" not in p and p["limit"] == 150


@pytest.mark.asyncio
async def test_hotels_fall_back_to_city_name_when_radius_finds_none():
    prov = NuiteeHotelProvider(api_key="k", base_url="https://x")
    client = _Client([[], [{"id": "h2", "name": "City Hotel"}]])
    found = await prov._fetch_static_hotels(client, _req(latitude=34.15, longitude=77.58))
    assert list(found) == ["h2"]
    assert client.params[1]["cityName"] == "Ladakh"
    assert any("city name" in n for n in prov.last_notes)


def test_rates_payload_uses_coordinates_without_hotel_ids():
    prov = NuiteeHotelProvider(api_key="k", base_url="https://x")
    payload = prov._build_rates_payload(_req(latitude=34.15, longitude=77.58, radius_km=12))
    assert payload["radius"] == 12000 and "cityName" not in payload


def _opt(oid, price, stars):
    start = date.today() + timedelta(days=30)
    return HotelOption(option_id=oid, provider_hotel_id=oid, hotel_name=oid, check_in=start,
                       check_out=start + timedelta(days=2), nights=2, total_price=Decimal(price), currency="INR",
                       price_per_night=Decimal(price) / 2, star_rating=stars, provider_name="t",
                       retrieved_at="2026-01-01T00:00:00")


def test_unrated_budget_stay_is_not_ranked_as_zero_stars():
    cheap_unrated = _opt("guesthouse", "2400", None)
    pricey_rated = _opt("resort", "24000", 5.0)
    mid = _opt("mid", "9000", 3.0)
    ranked = rank_hotel_options([pricey_rated, mid, cheap_unrated], HotelPreferences(priority="balanced"))
    assert ranked[0].option_id == "guesthouse"
