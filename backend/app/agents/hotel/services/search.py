import asyncio
import logging
from collections import Counter
from typing import Dict, List, Optional

from app.agents.hotel.calculations.distance import nearest_reference_km
from app.agents.hotel.calculations.pricing import comparable_price
from app.agents.hotel.calculations.ranking import rank_hotel_options
from app.agents.hotel.providers.base import BaseHotelProvider
from app.agents.hotel.providers.hotel_nuitee import NuiteeHotelProvider
from app.agents.hotel.schemas import (
    BoardType,
    HotelOption,
    HotelPreferences,
    HotelSearchRequest,
    HotelSearchResult,
)
from app.agents.hotel.validation.results import validate_option
from app.agents.hotel.validation.stay import validate_stay_request

logger = logging.getLogger(__name__)


def _matches_any(needles: List[str], haystack: List[str]) -> bool:
    """True if every needle is found (case-insensitive substring) in some haystack entry."""
    lowered = [h.lower() for h in haystack]
    return all(any(n.lower() in h for h in lowered) for n in needles)


class HotelSearchService:
    """
    Coordinates accommodation searches across providers, normalizes/validates results,
    filters hard constraints, and ranks the survivors (TDD section 8.4).
    Unlike a bare list, it reports WHY results are missing (provider failures, constraints that
    removed everything) so nothing is silently relaxed (TDD 8.2 #10, 8.7).
    """

    def __init__(self, providers: Optional[List[BaseHotelProvider]] = None):
        self.providers = providers if providers is not None else [NuiteeHotelProvider()]

    def add_provider(self, provider: BaseHotelProvider):
        self.providers.append(provider)

    # ------------------------------------------------------------------ main entry
    async def search(self, request: HotelSearchRequest) -> HotelSearchResult:
        limitations: List[str] = []

        problems = validate_stay_request(request)
        if problems:
            return HotelSearchResult(
                query=request, options=[], limitations=[f"Invalid request: {p}" for p in problems]
            )

        # 1. Query providers concurrently; keep failures visible
        outcomes = await asyncio.gather(
            *(p.search(request) for p in self.providers), return_exceptions=True
        )
        candidates: List[HotelOption] = []
        any_provider_ok = False
        for provider, outcome in zip(self.providers, outcomes):
            if isinstance(outcome, Exception):
                logger.error("Provider %s search failed: %s", provider.name, outcome)
                limitations.append(f"Provider {provider.name} failed: {outcome}")
                continue
            any_provider_ok = True
            candidates.extend(outcome)
            limitations.extend(getattr(provider, "last_notes", []) or [])

        # 2. De-duplicate by option_id
        unique: Dict[str, HotelOption] = {}
        for opt in candidates:
            unique.setdefault(opt.option_id, opt)
        candidates = list(unique.values())

        # 3. Mechanical validation (currency, dates, nights, rooms)
        valid: List[HotelOption] = []
        invalid_reasons: Counter = Counter()
        for opt in candidates:
            issues = validate_option(opt, request)
            if issues:
                invalid_reasons.update(issues)
            else:
                valid.append(opt)
        for reason, n in invalid_reasons.items():
            limitations.append(f"Dropped {n} option(s): {reason}.")

        # 4. Hard constraints
        filtered, rejected = self.apply_hard_constraints(valid, request, limitations)

        # 5. Rank, then cap per hotel and overall
        ranked = rank_hotel_options(filtered, request.preferences)
        final = self._cap_results(ranked, request)

        # 6. Explain empty outcomes
        if not final:
            if any_provider_ok and not candidates:
                limitations.append(
                    f"No availability returned for {request.destination} "
                    f"({request.check_in} to {request.check_out})."
                )
            elif candidates and rejected:
                detail = ", ".join(f"{k} removed {v}" for k, v in rejected.items())
                limitations.append(
                    f"{len(valid)} option(s) found but none satisfy the hard constraints ({detail}). "
                    "Constraints were not relaxed."
                )

        return HotelSearchResult(
            query=request, options=final, limitations=limitations, rejected_counts=dict(rejected)
        )

    async def search_and_rank(self, request: HotelSearchRequest) -> List[HotelOption]:
        """List-only convenience wrapper (mirrors TransportSearchService.search_and_rank)."""
        return (await self.search(request)).options

    # ------------------------------------------------------------------ filtering
    @staticmethod
    def apply_hard_constraints(
        options: List[HotelOption], request: HotelSearchRequest, limitations: List[str]
    ) -> tuple[List[HotelOption], Counter]:
        """
        Remove options violating hard requirements (TDD 8.2 #4). Unverifiable star/refund/board/distance
        data counts as a violation. Amenity/accessibility needs can only be enforced when the provider
        supplied amenity data; otherwise the option is kept, flagged 'unverified', and reported.
        """
        c = request.constraints
        max_room_guests = max(r.total_guests for r in request.rooms)
        rejected: Counter = Counter()
        kept: List[HotelOption] = []
        unverified_amenity = 0

        for opt in options:
            price = comparable_price(opt.all_in_price, opt.total_price)

            if c.max_total_price is not None and price > c.max_total_price:
                rejected["max_total_price"] += 1
                continue
            if c.max_price_per_night is not None and (price / opt.nights) > c.max_price_per_night:
                rejected["max_price_per_night"] += 1
                continue
            if c.min_star_rating is not None and (opt.star_rating is None or opt.star_rating < c.min_star_rating):
                rejected["min_star_rating"] += 1
                continue
            if c.refundable_only and opt.refundable is not True:
                rejected["refundable_only"] += 1
                continue
            if c.required_board_types and opt.board_type not in c.required_board_types:
                rejected["required_board_types"] += 1
                continue
            if opt.max_occupancy is not None and opt.max_occupancy < max_room_guests:
                rejected["occupancy"] += 1
                continue
            if c.max_distance_km is not None:
                nearest = nearest_reference_km(opt.latitude, opt.longitude, request.preferences.reference_points)
                if nearest is None or nearest > c.max_distance_km:
                    rejected["max_distance_km"] += 1
                    continue

            needs = [*c.required_amenities, *c.accessibility_needs]
            if needs:
                if opt.amenities:
                    if not _matches_any(needs, opt.amenities):
                        rejected["required_amenities"] += 1
                        continue
                else:
                    unverified_amenity += 1
                    opt.warnings.append(
                        "Required amenities/accessibility needs could not be verified from provider data."
                    )

            kept.append(opt)

        if unverified_amenity:
            limitations.append(
                f"{unverified_amenity} option(s) kept although required amenities/accessibility could not be "
                "verified (provider returned no amenity data). Confirm with the property."
            )
        return kept, rejected

    @staticmethod
    def _cap_results(ranked: List[HotelOption], request: HotelSearchRequest) -> List[HotelOption]:
        per_hotel: Counter = Counter()
        final: List[HotelOption] = []
        for opt in ranked:
            if per_hotel[opt.provider_hotel_id] >= request.max_options_per_hotel:
                continue
            per_hotel[opt.provider_hotel_id] += 1
            final.append(opt)
            if len(final) >= request.max_results:
                break
        return final

    # ------------------------------------------------------------------ re-ranking (TDD 8.7 #6)
    @staticmethod
    def rerank(options: List[HotelOption], preferences: HotelPreferences) -> List[HotelOption]:
        """Re-rank previously retrieved options (e.g. once itinerary locations are known). No new provider call."""
        return rank_hotel_options(options, preferences)
