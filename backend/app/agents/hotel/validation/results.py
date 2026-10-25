"""Mechanical sanity checks on normalized options (TDD 4.4: application code, not the LLM, validates)."""
from decimal import Decimal
from typing import List

from app.agents.hotel.schemas import HotelOption, HotelSearchRequest


def validate_option(option: HotelOption, request: HotelSearchRequest) -> List[str]:
    """Return problems that make an option unsafe to present. Empty list == OK."""
    problems: List[str] = []
    if option.total_price <= Decimal("0"):
        problems.append("non-positive price")
    if option.currency != request.currency:
        problems.append(f"currency {option.currency} differs from requested {request.currency}")
    if option.check_in != request.check_in or option.check_out != request.check_out:
        problems.append("stay dates differ from request")
    if option.nights != request.nights:
        problems.append("night count differs from request")
    if option.rooms_count != len(request.rooms):
        problems.append("room count differs from request")
    return problems


def staleness_warning(option: HotelOption, max_age_minutes: int = 30, now=None) -> str | None:
    """Prices/availability are only guaranteed at retrieval time; flag old results."""
    from datetime import datetime
    now = now or datetime.utcnow()
    age = (now - option.retrieved_at).total_seconds() / 60
    if age > max_age_minutes:
        return f"Price/availability retrieved {int(age)} minutes ago; refresh before presenting as current."
    return None
