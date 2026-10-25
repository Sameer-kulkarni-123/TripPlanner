"""Deterministic ranking for hotel options.

S = w_c * C + w_q * Q + w_l * L + w_f * F
  C = normalized cost score (all-in price when known)
  Q = quality score (star rating)
  L = location score (mean straight-line distance to reference points)
  F = flexibility/fit score (cancellation terms + meal-plan preference)
Weights sum to 1; higher is better. A component that cannot be computed for ANY option
(e.g. no reference points -> no L) is dropped and the remaining weights are re-normalized,
so missing data never silently rewards or penalizes options.
"""
from typing import Dict, List, Optional

from app.agents.hotel.calculations.distance import mean_reference_km, DISTANCE_SOURCE
from app.agents.hotel.calculations.pricing import comparable_price
from app.agents.hotel.schemas import HotelOption, HotelPreferences

WEIGHTS: Dict[str, Dict[str, float]] = {
    "cheapest":              {"C": 0.55, "Q": 0.15, "L": 0.15, "F": 0.15},
    "best_rated":            {"C": 0.15, "Q": 0.55, "L": 0.15, "F": 0.15},
    "location":              {"C": 0.15, "Q": 0.15, "L": 0.55, "F": 0.15},
    "flexible_cancellation": {"C": 0.15, "Q": 0.15, "L": 0.15, "F": 0.55},
    "balanced":              {"C": 0.35, "Q": 0.25, "L": 0.25, "F": 0.15},
}


def _normalize_min_better(val: float, min_v: float, max_v: float) -> float:
    if max_v == min_v:
        return 1.0
    return 1.0 - ((val - min_v) / (max_v - min_v))


def _normalize_max_better(val: float, min_v: float, max_v: float) -> float:
    if max_v == min_v:
        return 1.0
    return (val - min_v) / (max_v - min_v)


def _flexibility_score(opt: HotelOption, prefs: HotelPreferences) -> float:
    """0..1: refundable/free-cancellation terms (0.7 weight) + preferred meal plan (0.3 weight)."""
    if opt.refundable is True:
        cancel = 1.0 if opt.free_cancellation_until else 0.8
    elif opt.refundable is False:
        cancel = 0.0
    else:
        cancel = 0.4  # unknown policy: neither rewarded like refundable nor punished like non-refundable
    if prefs.preferred_board_types:
        board = 1.0 if opt.board_type in prefs.preferred_board_types else 0.0
    else:
        board = 0.5
    return 0.7 * cancel + 0.3 * board


def rank_hotel_options(options: List[HotelOption], preferences: HotelPreferences) -> List[HotelOption]:
    """Score and sort options (best first). Mutates ranking_score / distance fields on the options."""
    if not options:
        return []

    # Location: compute distance for each option (None when coordinates or reference points are missing)
    for opt in options:
        dist = mean_reference_km(opt.latitude, opt.longitude, preferences.reference_points)
        opt.distance_km_to_reference = dist
        opt.distance_source = DISTANCE_SOURCE if dist is not None else None

    if len(options) == 1:
        options[0].ranking_score = 1.0
        return options

    weights = dict(WEIGHTS.get(preferences.priority, WEIGHTS["balanced"]))

    prices = [float(comparable_price(o.all_in_price, o.total_price)) for o in options]
    min_p, max_p = min(prices), max(prices)

    stars = [o.star_rating for o in options if o.star_rating is not None]
    dists = [o.distance_km_to_reference for o in options if o.distance_km_to_reference is not None]

    # Drop components with no data for any option; re-normalize the remaining weights
    if not stars:
        weights.pop("Q")
    if not dists:
        weights.pop("L")
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    for opt, price in zip(options, prices):
        parts: Dict[str, float] = {"C": _normalize_min_better(price, min_p, max_p)}
        if "Q" in weights:
            # Unknown star rating among rated options gets a neutral 0.0 star (penalized, flagged)
            s = opt.star_rating if opt.star_rating is not None else 0.0
            parts["Q"] = _normalize_max_better(s, min(stars), max(stars)) if opt.star_rating is not None else 0.0
        if "L" in weights:
            d: Optional[float] = opt.distance_km_to_reference
            parts["L"] = _normalize_min_better(d, min(dists), max(dists)) if d is not None else 0.0
        parts["F"] = _flexibility_score(opt, preferences)

        score = sum(weights[k] * parts[k] for k in weights)
        opt.ranking_score = round(score, 4)

    # Stable, deterministic tie-break: score desc, then cheaper, then option_id
    return sorted(
        options,
        key=lambda o: (-(o.ranking_score or 0.0), float(comparable_price(o.all_in_price, o.total_price)), o.option_id),
    )
