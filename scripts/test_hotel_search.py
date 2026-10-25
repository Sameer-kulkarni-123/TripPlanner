r"""
Script to test real-time hotel search via the Hotel Agent and Nuitee/LiteAPI.
Run using:
    .\.venv\Scripts\python scripts/test_hotel_search.py
"""
import sys
import os
import asyncio
from datetime import date, timedelta

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.agents.hotel.schemas import (
    HotelSearchRequest,
    HotelPreferences,
    HotelSearchConstraints,
    RoomOccupancy,
    GeoPoint,
)
from app.agents.hotel.services.search import HotelSearchService


async def test_live_search():
    print("=" * 60)
    print("Hotel Agent: Live Hotel Search Verification")
    print("=" * 60)

    api_key = settings.NUITEE_API_KEY
    if not api_key:
        print("[!] ERROR: NUITEE_API_KEY is not configured in .env file.")
        return

    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"API Key: {masked_key}")
    print(f"Base URL: {settings.NUITEE_API_BASE_URL}")

    check_in = date.today() + timedelta(days=30)
    check_out = check_in + timedelta(days=3)

    print(f"\nSearching hotels: Paris, FR | {check_in} -> {check_out} | 2 adults, 1 room")
    print("Priority: balanced (reference point: Eiffel Tower)\n")

    request = HotelSearchRequest(
        destination="Paris",
        country_code="FR",
        check_in=check_in,
        check_out=check_out,
        rooms=[RoomOccupancy(adults=2)],
        currency="USD",
        preferences=HotelPreferences(
            priority="balanced",
            reference_points=[GeoPoint(name="Eiffel Tower", latitude=48.8584, longitude=2.2945)],
        ),
        constraints=HotelSearchConstraints(),
        max_results=5,
    )

    service = HotelSearchService()
    result = await service.search(request)

    for note in result.limitations:
        print(f"[note] {note}")

    if not result.options:
        print("[x] No hotel options returned. Check the notes above and backend logs.")
        return

    print(f"\n[✓] SUCCESS! Top {len(result.options)} ranked option(s):\n")
    for i, opt in enumerate(result.options, start=1):
        print(f"--- Option {i} (Ranking Score: {opt.ranking_score}) ---")
        print(f"  Hotel: {opt.hotel_name} ({opt.star_rating or '?'}★) | {opt.address or 'address n/a'}")
        print(f"  Room: {opt.room_name} | Board: {opt.board_type.value}")
        print(f"  Total ({opt.nights} nights, {opt.rooms_count} room): {opt.currency} {opt.total_price}"
              f"  (~{opt.price_per_night}/night)")
        if opt.excluded_charges_total:
            print(f"  Payable at property: {opt.currency} {opt.excluded_charges_total} -> all-in {opt.all_in_price}")
        print(f"  Cancellation: {opt.cancellation_summary}")
        if opt.distance_km_to_reference is not None:
            print(f"  Distance to reference: {opt.distance_km_to_reference} km ({opt.distance_source})")
        for w in opt.warnings:
            print(f"  ! {w}")
        print()


if __name__ == "__main__":
    asyncio.run(test_live_search())
