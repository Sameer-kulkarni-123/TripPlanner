r"""
Script to test real-time flight search via Travel Agent and Nuitee/LiteAPI.
Run using:
    .\.venv\Scripts\python scripts/test_flight_search.py
"""
import sys
import os
import asyncio
from datetime import date, timedelta

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.agents.travel.schemas import TravelSearchRequest, TravelPreferences, TravelSearchConstraints
from app.agents.travel.services.search import TransportSearchService


async def test_live_search():
    print("=" * 60)
    print("Travel Agent: Live Flight Search Verification")
    print("=" * 60)

    api_key = settings.NUITEE_API_KEY
    if not api_key:
        print("[!] ERROR: NUITEE_API_KEY is not configured in .env file.")
        return

    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"API Key: {masked_key}")
    print(f"Base URL: {settings.NUITEE_API_BASE_URL}")

    # Departure 30 days from today (compliant with 11-month limit)
    dep_date = date.today() + timedelta(days=30)
    ret_date = dep_date + timedelta(days=7)

    origin = "JFK"
    destination = "LHR"

    print(f"\nSearching flights:")
    print(f"  Origin: {origin}")
    print(f"  Destination: {destination}")
    print(f"  Departure: {dep_date}")
    print(f"  Return: {ret_date}")
    print(f"  Passengers: 1 Adult")
    print(f"  Priority: cheapest")
    print("\nSending request to Nuitee/LiteAPI...\n")

    request = TravelSearchRequest(
        origin=origin,
        destination=destination,
        departure_date=dep_date,
        return_date=ret_date,
        preferences=TravelPreferences(priority="cheapest"),
        constraints=TravelSearchConstraints(max_transfers=1),
        currency="USD"
    )

    service = TransportSearchService()
    options = await service.search_and_rank(request)

    if not options:
        print("[x] No flight options returned. Possible reasons:")
        print("    1. Sandbox API key permissions or test route limitations.")
        print("    2. Network connectivity to LiteAPI endpoint.")
        print("    Check backend logs for detailed HTTP response code.")
        return

    print(f"[✓] SUCCESS! Found and ranked {len(options)} option(s):\n")
    for i, opt in enumerate(options[:5], start=1):
        print(f"--- Option {i} (Ranking Score: {opt.ranking_score}) ---")
        print(f"  Option ID: {opt.option_id}")
        print(f"  Provider: {opt.provider_name}")
        print(f"  Route: {opt.origin_name} -> {opt.destination_name}")
        print(f"  Times: Depart {opt.departure_time} | Arrive {opt.arrival_time}")
        print(f"  Duration: {opt.duration_minutes} mins | Transfers/Stops: {opt.transfers}")
        print(f"  Price: {opt.currency} {opt.price}")
        if opt.baggage_summary:
            print(f"  Baggage: {opt.baggage_summary}")
        if opt.segments:
            print(f"  Segments ({len(opt.segments)}):")
            for seg in opt.segments:
                carrier = f"{seg.carrier_name or seg.carrier_code or 'Flight'} {seg.vehicle_or_flight_number or ''}"
                print(f"    - {carrier}: {seg.departure_location} -> {seg.arrival_location} ({seg.duration_minutes}m)")
        print()


if __name__ == "__main__":
    asyncio.run(test_live_search())
