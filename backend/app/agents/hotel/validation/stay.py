"""Validation of stay requirements before any provider call (TDD 8.4: 'Validate destination, dates, and occupancy')."""
from datetime import date
from typing import List, Optional

from app.agents.hotel.schemas import HotelSearchRequest

MAX_NIGHTS = 30
MAX_ROOMS = 5
MAX_ADVANCE_DAYS = 330  # ~11 months, mirrors the provider horizon used for flights


def validate_stay_request(request: HotelSearchRequest, today: Optional[date] = None) -> List[str]:
    """Return a list of human-readable problems. Empty list means the request is searchable."""
    today = today or date.today()
    problems: List[str] = []

    if not request.destination.strip():
        problems.append("Destination city is required.")
    if request.check_out <= request.check_in:
        problems.append("check_out must be after check_in.")
    else:
        if request.nights > MAX_NIGHTS:
            problems.append(f"Stays longer than {MAX_NIGHTS} nights are not supported in a single search.")
    if request.check_in < today:
        problems.append("check_in is in the past.")
    if (request.check_in - today).days > MAX_ADVANCE_DAYS:
        problems.append("check_in is too far in the future for provider availability.")
    if len(request.rooms) > MAX_ROOMS:
        problems.append(f"At most {MAX_ROOMS} rooms are supported per search.")
    if len(request.currency) != 3:
        problems.append("currency must be a 3-letter ISO code.")
    return problems
