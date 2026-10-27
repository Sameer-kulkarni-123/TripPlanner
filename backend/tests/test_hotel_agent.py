from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.agents.hotel.agent import HotelAgent
from app.agents.hotel.calculations.distance import haversine_km
from app.agents.hotel.calculations.pricing import calculate_nights, price_per_night
from app.agents.hotel.calculations.ranking import rank_hotel_options
from app.agents.hotel.providers.base import BaseHotelProvider, HotelProviderError
from app.agents.hotel.providers.hotel_nuitee import NuiteeHotelProvider, map_board_type
from app.agents.hotel.schemas import (
    BoardType,
    GeoPoint,
    HotelOption,
    HotelPreferences,
    HotelSearchConstraints,
    HotelSearchRequest,
    RoomOccupancy,
)
from app.agents.hotel.services.search import HotelSearchService
from app.agents.hotel.validation.stay import validate_stay_request

CHECK_IN = date.today() + timedelta(days=60)
CHECK_OUT = CHECK_IN + timedelta(days=3)


def make_request(**kw) -> HotelSearchRequest:
    base = dict(destination="Rome", country_code="IT", check_in=CHECK_IN, check_out=CHECK_OUT)
    base.update(kw)
    return HotelSearchRequest(**base)


def make_option(opt_id="o1", hotel="h1", price="300.00", stars=4.0, refundable=True,
                lat=41.90, lon=12.49, board=BoardType.ROOM_ONLY, **kw) -> HotelOption:
    total = Decimal(price)
    data = dict(
        option_id=opt_id, provider_hotel_id=hotel, hotel_name=f"Hotel {hotel}",
        star_rating=stars, latitude=lat, longitude=lon, board_type=board,
        check_in=CHECK_IN, check_out=CHECK_OUT, nights=3, total_price=total, currency="USD",
        price_per_night=price_per_night(total, 3), refundable=refundable, provider_name="Mock",
    )
    data.update(kw)
    return HotelOption(**data)


class MockHotelProvider(BaseHotelProvider):
    def __init__(self, options=None, fail=False):
        self._options, self._fail = options or [], fail

    @property
    def name(self): return "MockHotels"
    async def is_available(self): return True
    async def search(self, request):
        if self._fail:
            raise HotelProviderError("boom")
        return self._options


# ---------------------------------------------------------------- calculations
def test_nights_and_price_per_night():
    assert calculate_nights(date(2026, 11, 1), date(2026, 11, 4)) == 3
    assert price_per_night(Decimal("100.00"), 3) == Decimal("33.33")
    with pytest.raises(ValueError):
        price_per_night(Decimal("100"), 0)


def test_haversine_known_distance():
    # Colosseum -> Vatican City is roughly 3.5-4.5 km
    assert 3.0 < haversine_km(41.8902, 12.4922, 41.9029, 12.4534) < 4.5


def test_rank_cheapest_prefers_lower_price():
    cheap = make_option("cheap", "a", "200.00", stars=3)
    pricey = make_option("pricey", "b", "600.00", stars=3)
    ranked = rank_hotel_options([pricey, cheap], HotelPreferences(priority="cheapest"))
    assert ranked[0].option_id == "cheap"
    assert ranked[0].ranking_score > ranked[1].ranking_score


def test_rank_location_uses_reference_points():
    near = make_option("near", "a", "500.00", lat=41.8902, lon=12.4922)
    far = make_option("far", "b", "200.00", lat=41.99, lon=12.70)
    prefs = HotelPreferences(priority="location", reference_points=[GeoPoint(name="Colosseum", latitude=41.8902, longitude=12.4922)])
    ranked = rank_hotel_options([far, near], prefs)
    assert ranked[0].option_id == "near"
    assert ranked[0].distance_km_to_reference is not None
    assert "not travel time" in ranked[0].distance_source


def test_rank_without_reference_points_ignores_location():
    a = make_option("a", "a", "200.00", lat=None, lon=None)
    b = make_option("b", "b", "300.00", lat=None, lon=None)
    ranked = rank_hotel_options([b, a], HotelPreferences(priority="location"))
    assert all(o.distance_km_to_reference is None for o in ranked)
    assert ranked[0].option_id == "a"  # falls back on remaining components, cheaper wins ties


# ---------------------------------------------------------------- validation
def test_validate_stay_request():
    assert validate_stay_request(make_request()) == []
    bad = make_request(check_in=date.today() - timedelta(days=2), check_out=date.today() - timedelta(days=5))
    problems = validate_stay_request(bad)
    assert any("after check_in" in p for p in problems)
    assert any("past" in p for p in problems)


# ---------------------------------------------------------------- service
@pytest.mark.asyncio
async def test_hard_constraints_filter_and_report():
    opts = [
        make_option("ok", "a", "400.00", stars=4, refundable=True),
        make_option("too-pricey", "b", "900.00", stars=5, refundable=True),
        make_option("low-star", "c", "300.00", stars=2, refundable=True),
        make_option("nonref", "d", "350.00", stars=4, refundable=False),
    ]
    service = HotelSearchService(providers=[MockHotelProvider(opts)])
    req = make_request(constraints=HotelSearchConstraints(
        max_total_price=Decimal("500"), min_star_rating=3, refundable_only=True))
    result = await service.search(req)
    assert [o.option_id for o in result.options] == ["ok"]
    assert result.rejected_counts == {"max_total_price": 1, "min_star_rating": 1, "refundable_only": 1}


@pytest.mark.asyncio
async def test_all_filtered_explains_without_relaxing():
    service = HotelSearchService(providers=[MockHotelProvider([make_option(price="900.00")])])
    result = await service.search(make_request(constraints=HotelSearchConstraints(max_total_price=Decimal("100"))))
    assert result.options == []
    assert any("none satisfy the hard constraints" in l for l in result.limitations)


@pytest.mark.asyncio
async def test_excluded_fees_count_toward_budget():
    opt = make_option(price="480.00", excluded_charges_total=Decimal("40.00"), all_in_price=Decimal("520.00"))
    service = HotelSearchService(providers=[MockHotelProvider([opt])])
    result = await service.search(make_request(constraints=HotelSearchConstraints(max_total_price=Decimal("500"))))
    assert result.options == []


@pytest.mark.asyncio
async def test_provider_failure_is_reported_not_hidden():
    service = HotelSearchService(providers=[MockHotelProvider(fail=True)])
    result = await service.search(make_request())
    assert result.options == []
    assert any("MockHotels failed" in l for l in result.limitations)


@pytest.mark.asyncio
async def test_wrong_currency_dropped_and_per_hotel_cap():
    opts = [make_option(f"o{i}", "same", str(100 + i)) for i in range(4)]
    opts.append(make_option("eur", "x", "100.00", currency="EUR"))
    service = HotelSearchService(providers=[MockHotelProvider(opts)])
    result = await service.search(make_request(max_options_per_hotel=2))
    assert len(result.options) == 2
    assert all(o.currency == "USD" for o in result.options)
    assert any("currency" in l for l in result.limitations)


@pytest.mark.asyncio
async def test_unverifiable_amenities_kept_but_flagged():
    service = HotelSearchService(providers=[MockHotelProvider([make_option()])])
    result = await service.search(make_request(constraints=HotelSearchConstraints(required_amenities=["pool"])))
    assert len(result.options) == 1
    assert any("could not be verified" in w for w in result.options[0].warnings)


# ---------------------------------------------------------------- agent
@pytest.mark.asyncio
async def test_agent_execute_success_and_invalid():
    agent = HotelAgent(HotelSearchService(providers=[MockHotelProvider([make_option()])]))
    ok = await agent.execute({
        "destination": "Rome", "country_code": "IT",
        "check_in": CHECK_IN.isoformat(), "check_out": CHECK_OUT.isoformat(),
        "rooms": [{"adults": 2}],
    })
    assert ok["status"] == "success" and ok["options_count"] == 1
    assert ok["accommodation_options"][0]["price_basis"] == "total_stay_all_rooms"

    bad = await agent.execute({"destination": "Rome"})
    assert bad["status"] == "invalid_request"


@pytest.mark.asyncio
async def test_agent_rerank_without_new_search():
    agent = HotelAgent(HotelSearchService(providers=[MockHotelProvider(fail=True)]))
    near = make_option("near", "a", "500.00", lat=41.8902, lon=12.4922).model_dump(mode="json")
    far = make_option("far", "b", "200.00", lat=41.99, lon=12.70).model_dump(mode="json")
    out = await agent.rerank({
        "accommodation_options": [far, near],
        "preferences": {"priority": "location",
                        "reference_points": [{"name": "Colosseum", "latitude": 41.8902, "longitude": 12.4922}]},
    })
    assert out["accommodation_options"][0]["option_id"] == "near"


# ---------------------------------------------------------------- Nuitee parsing
RATES_FIXTURE = {
    "data": [{
        "hotelId": "lp123",
        "roomTypes": [
            {
                "roomTypeId": "RT1", "offerId": "OFFER-ABC", "supplier": "nuitee",
                "offerRetailRate": {"amount": 450.0, "currency": "USD"},
                "rates": [{
                    "rateId": "R1", "name": "Standard Double", "maxOccupancy": 2,
                    "boardType": "BB", "boardName": "Breakfast included",
                    "retailRate": {
                        "total": [{"amount": 450.0, "currency": "USD"}],
                        "taxesAndFees": [
                            {"included": True, "description": "VAT", "amount": 40.0, "currency": "USD"},
                            {"included": False, "description": "City tax", "amount": 12.0, "currency": "USD"},
                        ],
                    },
                    "cancellationPolicies": {
                        "refundableTag": "RFN",
                        "cancelPolicyInfos": [{"cancelTime": "2026-12-01T23:59:00Z", "amount": 150.0, "type": "amount"}],
                        "hotelRemarks": ["Pay city tax at property"],
                    },
                    "paymentTypes": ["NUITEE_PAY"],
                }],
            },
            {   # no offerRetailRate -> summed from rates; non-refundable
                "roomTypeId": "RT2", "offerId": "OFFER-DEF",
                "rates": [{
                    "rateId": "R2", "name": "Budget Single", "boardType": "RO", "occupancyNumber": 1,
                    "retailRate": {"total": [{"amount": 300.0, "currency": "USD"}]},
                    "cancellationPolicies": {"refundableTag": "NRFN"},
                }],
            },
            {"roomTypeId": "BROKEN", "rates": [{"retailRate": {"total": "garbage"}}]},
        ],
    }]
}
STATIC_FIXTURE = {"lp123": {
    "name": "Hotel Roma", "address": "Via Roma 1", "city": "Rome", "country_code": "it",
    "latitude": 41.9, "longitude": 12.5, "star_rating": 4.0, "guest_rating": 8.4,
    "main_photo_url": None, "amenities": [],
}}


def test_map_board_type():
    assert map_board_type("BB", None) == BoardType.BREAKFAST
    assert map_board_type(None, "All-Inclusive") == BoardType.ALL_INCLUSIVE
    assert map_board_type(None, None) == BoardType.UNKNOWN


def test_nuitee_payload_shape():
    p = NuiteeHotelProvider(api_key="k", base_url="https://x")
    req = make_request(rooms=[RoomOccupancy(adults=2, children_ages=[5]), RoomOccupancy(adults=1)],
                       constraints=HotelSearchConstraints(refundable_only=True))
    payload = p._build_rates_payload(req, ["lp1"])
    assert payload["occupancies"] == [{"adults": 2, "children": [5]}, {"adults": 1, "children": []}]
    assert payload["hotelIds"] == ["lp1"] and payload["refundableRatesOnly"] is True
    assert payload["checkin"] == CHECK_IN.isoformat()
    by_city = p._build_rates_payload(req)
    assert by_city["cityName"] == "Rome" and by_city["countryCode"] == "IT"


def test_nuitee_parse_rates_response():
    p = NuiteeHotelProvider(api_key="k", base_url="https://x")
    req = make_request(rooms=[RoomOccupancy(adults=2)])
    opts = p._parse_rates_response(RATES_FIXTURE, req, STATIC_FIXTURE)
    assert len(opts) == 2  # broken offer skipped
    assert any("no usable price" in n for n in p.last_notes)

    a = next(o for o in opts if o.room_type_id == "RT1")
    assert a.hotel_name == "Hotel Roma" and a.star_rating == 4.0
    assert a.board_type == BoardType.BREAKFAST
    assert a.total_price == Decimal("450.00") and a.nights == 3
    assert a.price_per_night == Decimal("150.00")
    assert a.excluded_charges_total == Decimal("12.00") and a.all_in_price == Decimal("462.00")
    assert a.refundable is True and a.free_cancellation_until is not None
    assert a.provider_name == "Nuitee (nuitee)"

    b = next(o for o in opts if o.room_type_id == "RT2")
    assert b.total_price == Decimal("300.00") and b.refundable is False
