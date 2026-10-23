"""Deterministic calculation tools for travel ranking and scoring.
As specified in Section 5.7 and 5.10 of TDD:
S = w_c * C + w_t * T + w_x * X + w_p * P
Higher score indicates more desirable option.
"""
from typing import List, Tuple
from decimal import Decimal
from app.agents.travel.schemas import TransportOption, TravelPreferences


def calculate_journey_duration(departure_time, arrival_time) -> int:
    """Returns duration in minutes between departure and arrival."""
    delta = arrival_time - departure_time
    return int(delta.total_seconds() // 60)


def rank_transport_options(
    options: List[TransportOption],
    preferences: TravelPreferences,
) -> List[TransportOption]:
    """
    Ranks options deterministically based on:
    - Normalized Cost (C)
    - Normalized Duration (T)
    - Transfers / Convenience (X)
    - Preference Fit (P)
    Weights sum to 1.0.
    """
    if not options:
        return []

    # If only 1 option, perfect score
    if len(options) == 1:
        options[0].ranking_score = 1.0
        return options

    # Configure weights based on priority
    if preferences.priority == "cheapest":
        w_c, w_t, w_x, w_p = 0.50, 0.20, 0.15, 0.15
    elif preferences.priority == "fastest":
        w_c, w_t, w_x, w_p = 0.20, 0.50, 0.15, 0.15
    elif preferences.priority == "fewest_transfers":
        w_c, w_t, w_x, w_p = 0.20, 0.20, 0.45, 0.15
    else:  # balanced
        w_c, w_t, w_x, w_p = 0.35, 0.30, 0.20, 0.15

    # Find min and max for normalization
    prices = [float(opt.price) for opt in options]
    durations = [opt.duration_minutes for opt in options]
    transfers = [opt.transfers for opt in options]

    min_p, max_p = min(prices), max(prices)
    min_d, max_d = min(durations), max(durations)
    min_x, max_x = min(transfers), max(transfers)

    def normalize_min_better(val: float, min_v: float, max_v: float) -> float:
        if max_v == min_v:
            return 1.0
        # Lower cost/duration/transfers gets higher score (1.0 = best, 0.0 = worst)
        return 1.0 - ((val - min_v) / (max_v - min_v))

    for opt in options:
        c_score = normalize_min_better(float(opt.price), min_p, max_p)
        t_score = normalize_min_better(float(opt.duration_minutes), min_d, max_d)
        x_score = normalize_min_better(float(opt.transfers), min_x, max_x)
        
        # Preference fit score:
        p_score = 1.0
        if preferences.avoid_carriers and opt.provider_name in preferences.avoid_carriers:
            p_score -= 0.5
        if preferences.preferred_carriers and opt.provider_name in preferences.preferred_carriers:
            p_score += 0.2
        p_score = max(0.0, min(1.0, p_score))

        # Overall weighted score
        final_score = (w_c * c_score) + (w_t * t_score) + (w_x * x_score) + (w_p * p_score)
        opt.ranking_score = round(final_score, 4)

    # Sort descending by score
    return sorted(options, key=lambda opt: opt.ranking_score or 0.0, reverse=True)
