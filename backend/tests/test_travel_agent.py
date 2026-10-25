from datetime import datetime, timedelta, date, timezone
from decimal import Decimal
import pytest

from app.agents.travel.schemas import (
    TransportOption,
    TransportMode,
    TravelPreferences,
    TravelSearchRequest,
    TravelSearchConstraints,
)
from app.agents.travel.calculations.ranking import (
    calculate_journey_duration,
    rank_transport_options,
)
from app.agents.travel.services.search import TransportSearchService
from app.agents.travel.providers.base import BaseTransportProvider


def test_calculate_journey_duration():
    dep = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    arr = datetime(2026, 11, 1, 13, 30, tzinfo=timezone.utc)
    assert calculate_journey_duration(dep, arr) == 210


def test_rank_transport_options_cheapest():
    now = datetime.now(timezone.utc)
    opt1 = TransportOption(
        option_id="opt-1",
        mode=TransportMode.FLIGHT,
        origin_name="London",
        destination_name="Rome",
        departure_time=now,
        arrival_time=now + timedelta(hours=3),
        duration_minutes=180,
        price=Decimal("150.00"),
        currency="USD",
        transfers=0,
        provider_name="Nuitee",
    )
    opt2 = TransportOption(
        option_id="opt-2",
        mode=TransportMode.FLIGHT,
        origin_name="London",
        destination_name="Rome",
        departure_time=now,
        arrival_time=now + timedelta(hours=2),
        duration_minutes=120,
        price=Decimal("250.00"),
        currency="USD",
        transfers=0,
        provider_name="Nuitee",
    )

    ranked = rank_transport_options([opt1, opt2], TravelPreferences(priority="cheapest"))
    # opt1 is cheaper ($150 vs $250), so with 'cheapest' priority, it should rank first
    assert ranked[0].option_id == "opt-1"
    assert ranked[0].ranking_score > ranked[1].ranking_score


class MockTransportProvider(BaseTransportProvider):
    @property
    def name(self) -> str:
        return "MockProvider"

    async def is_available(self) -> bool:
        return True

    async def search(self, request):
        now = datetime.now(timezone.utc)

        return [
            TransportOption(
                option_id="mock-1",
                mode=TransportMode.FLIGHT,
                origin_name=request.origin,
                destination_name=request.destination,
                departure_time=now,
                arrival_time=now + timedelta(hours=2),
                duration_minutes=120,
                price=Decimal("100.00"),
                currency=request.currency,
                transfers=0,
                provider_name=self.name,
            ),
            TransportOption(
                option_id="mock-2",
                mode=TransportMode.FLIGHT,
                origin_name=request.origin,
                destination_name=request.destination,
                departure_time=now,
                arrival_time=now + timedelta(hours=5),
                duration_minutes=300,
                price=Decimal("500.00"),
                currency=request.currency,
                transfers=2,
                provider_name=self.name,
            ),
        ]


@pytest.mark.asyncio
async def test_transport_search_service_filtering():
    service = TransportSearchService(providers=[MockTransportProvider()])
    req = TravelSearchRequest(
        origin="LHR",
        destination="FCO",
        departure_date=date(2026, 11, 1),
        constraints=TravelSearchConstraints(max_fare=Decimal("200.00")),
    )
    results = await service.search_and_rank(req)
    assert len(results) == 1
    assert results[0].option_id == "mock-1"


@pytest.mark.asyncio
async def test_missing_key_is_reported_not_silent():
    from app.agents.travel.providers.flight_nuitee import NuiteeFlightProvider
    provider = NuiteeFlightProvider(api_key="", base_url="https://example.invalid")
    provider.api_key = ""
    service = TransportSearchService(providers=[provider])
    req = TravelSearchRequest(origin="BLR", destination="CDG", departure_date=date(2026, 12, 8))
    options, limitations = await service.search_with_limitations(req)
    assert options == []
    assert any("NUITEE_API_KEY" in l for l in limitations)


@pytest.mark.asyncio
async def test_http_error_and_empty_results_are_explained(monkeypatch):
    import httpx
    from app.agents.travel.providers.flight_nuitee import NuiteeFlightProvider

    responses = iter([httpx.Response(403, text="forbidden"), httpx.Response(200, json={"data": []})])

    async def fake_post(self, url, json=None, headers=None):
        return next(responses)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = TransportSearchService(providers=[NuiteeFlightProvider(api_key="sand_test", base_url="https://x")])
    req = TravelSearchRequest(origin="BLR", destination="CDG", departure_date=date(2026, 12, 8))

    _, lim1 = await service.search_with_limitations(req)
    assert any("HTTP 403" in l and "Flights is enabled" in l for l in lim1)

    _, lim2 = await service.search_with_limitations(req)
    assert any("no fares" in l and "sandbox" in l for l in lim2)
