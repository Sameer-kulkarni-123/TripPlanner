"""Deterministic price arithmetic for the Hotel Agent (TDD 8.5 / 5.7: never use LLM arithmetic)."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from app.agents.hotel.schemas import TaxOrFee

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    """Convert any numeric-ish value to a 2dp Decimal (via str to avoid float artefacts)."""
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_nights(check_in: date, check_out: date) -> int:
    return (check_out - check_in).days


def price_per_night(total_price: Decimal, nights: int) -> Decimal:
    """Whole-booking price per night. Raises on non-positive nights to avoid silent bad comparisons."""
    if nights <= 0:
        raise ValueError("nights must be positive")
    return money(total_price / Decimal(nights))


def sum_excluded_charges(fees: Iterable[TaxOrFee], currency: str) -> tuple[Decimal, bool]:
    """
    Sum fees NOT included in the total price (usually payable at the property).
    Returns (sum_in_given_currency, had_foreign_currency_items).
    Fees in another currency are not converted (no exchange-rate source) and are not summed.
    """
    total = Decimal("0.00")
    foreign = False
    for fee in fees:
        if fee.included_in_total:
            continue
        if fee.currency != currency:
            foreign = True
            continue
        total += fee.amount
    return money(total), foreign


def all_in_price(total_price: Decimal, excluded_total: Decimal) -> Decimal:
    return money(total_price + excluded_total)


def comparable_price(all_in: Optional[Decimal], total_price: Decimal) -> Decimal:
    """Price used for budget filtering and ranking: all-in when known, else the provider total."""
    return all_in if all_in is not None else total_price
