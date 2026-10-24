"""Hard-constraint filtering, de-duplication and deterministic relevance scoring (TDD 7.2 #5)."""
import re
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List, Tuple

from app.agents.itinerary.schemas import Activity, AvailabilityStatus, ItineraryRequest, PriceBasis

INTEREST_KEYWORDS: Dict[str, List[str]] = {
    "history": ["history", "historic", "heritage", "castle", "fortress", "ancient", "monument", "ruins", "palace"],
    "art": ["art", "gallery", "painting", "museum", "sculpture", "artisan"],
    "museums": ["museum", "gallery", "exhibition"],
    "food": ["food", "culinary", "tasting", "cooking", "wine", "drink", "market", "tapas", "gastronomy", "dinner"],
    "nature": ["nature", "park", "garden", "hike", "hiking", "outdoors", "wildlife", "botanical"],
    "outdoors": ["outdoor", "hike", "bike", "kayak", "park", "beach", "nature"],
    "adventure": ["adventure", "kayak", "bike", "climb", "rafting", "zipline", "diving", "hike"],
    "nightlife": ["nightlife", "bar", "club", "pub", "jazz", "live music", "cocktail"],
    "music": ["music", "concert", "jazz", "opera", "live"],
    "culture": ["culture", "cultural", "local", "tradition", "workshop", "cooking class"],
    "architecture": ["architecture", "cathedral", "church", "basilica", "building", "rooftop"],
    "shopping": ["shopping", "market", "boutique", "bazaar", "souvenir"],
    "family": ["family", "kids", "children", "zoo", "aquarium", "science", "theme park"],
    "beach": ["beach", "coast", "seaside", "snorkel", "island"],
    "sightseeing": ["sightseeing", "tour", "viewpoint", "cruise", "landmark", "panoramic"],
    "relaxation": ["spa", "relax", "wellness", "thermal", "garden", "cruise"],
}

PRICE_EPS = Decimal("0.000001")


def _text(a: Activity) -> str:
    return " ".join([a.name or "", a.category or "", " ".join(a.categories), a.description or ""]).lower()


def _keywords_for(interest: str) -> List[str]:
    key = interest.strip().lower()
    return INTEREST_KEYWORDS.get(key, [key])


def _matches(text: str, kw: str) -> bool:
    return re.search(r"\b" + re.escape(kw.lower()), text) is not None


def matched_interests(a: Activity, interests: List[str]) -> List[str]:
    text = _text(a)
    return [i for i in interests if any(_matches(text, kw) for kw in _keywords_for(i))]


def is_must_include(a: Activity, must_include: List[str]) -> bool:
    name = (a.name or "").lower()
    return any(m == a.provider_activity_id or m == a.activity_id or (m and m.lower() in name) for m in must_include)


def deduplicate(activities: List[Activity]) -> List[Activity]:
    seen_ids, seen_names, out = set(), set(), []
    for a in activities:
        key_id = (a.provider_name, a.provider_activity_id)
        key_name = re.sub(r"[^a-z0-9]+", " ", (a.name or "").lower()).strip()
        if key_id in seen_ids or (key_name and key_name in seen_names):
            continue
        seen_ids.add(key_id)
        seen_names.add(key_name)
        out.append(a)
    return out


def filter_activities(
    activities: List[Activity], request: ItineraryRequest
) -> Tuple[List[Activity], List[Tuple[Activity, str]]]:
    """Return (kept, excluded_with_reason). Never relaxes hard constraints silently."""
    kept: List[Activity] = []
    excluded: List[Tuple[Activity, str]] = []

    needs = {n.lower() for n in request.travellers.accessibility_needs}
    youngest = min(request.travellers.child_ages) if request.travellers.child_ages else None
    trip_dates = {request.start_date + timedelta(days=i) for i in range(request.trip_days)}
    window_minutes = (
        request.daily_window.end.hour * 60 + request.daily_window.end.minute
        - request.daily_window.start.hour * 60 - request.daily_window.start.minute
    )

    for a in deduplicate(activities):
        forced = is_must_include(a, request.must_include)
        text = _text(a)

        if not forced and any(_matches(text, kw) for av in request.avoid for kw in _keywords_for(av)):
            excluded.append((a, "matches an 'avoid' preference"))
            continue

        if "wheelchair" in needs:
            if a.wheelchair_accessible is False:
                excluded.append((a, "not wheelchair accessible"))
                continue
            if a.wheelchair_accessible is None and "accessibility_unverified" not in a.confidence_flags:
                a.confidence_flags.append("accessibility_unverified")

        if youngest is not None and a.min_age is not None and youngest < a.min_age:
            excluded.append((a, f"minimum age {a.min_age} excludes a child traveller"))
            continue

        if request.budget.max_per_activity is not None and a.price is not None:
            if a.currency and a.currency.upper() != request.currency.upper():
                a.confidence_flags.append("currency_mismatch")
            else:
                per_person = a.price
                if a.price_basis == PriceBasis.PER_GROUP:
                    per_person = a.price / max(1, request.travellers.total)
                if per_person > request.budget.max_per_activity + PRICE_EPS:
                    excluded.append((a, "exceeds max price per activity"))
                    continue

        if request.max_activity_duration_minutes and a.duration_minutes > request.max_activity_duration_minutes:
            excluded.append((a, "exceeds max activity duration"))
            continue

        if a.duration_minutes > window_minutes:
            excluded.append((a, "longer than the daily activity window"))
            continue

        if a.available_dates is not None:
            if not trip_dates.intersection(a.available_dates):
                a.availability_status = AvailabilityStatus.UNAVAILABLE
                excluded.append((a, "provider reports no availability on trip dates"))
                continue
            a.availability_status = AvailabilityStatus.AVAILABLE

        a.matched_interests = matched_interests(a, request.interests)
        kept.append(a)

    return kept, excluded


def score_activities(activities: List[Activity], request: ItineraryRequest) -> List[Activity]:
    """Deterministic relevance score in [0,1] (+10 for must-include). Sorted descending."""
    priced = [float(a.price) for a in activities if a.price is not None]
    pmin, pmax = (min(priced), max(priced)) if priced else (0.0, 0.0)
    n_interests = len(request.interests)

    for a in activities:
        interest = (len(a.matched_interests) / n_interests) if n_interests else 0.5
        interest = min(1.0, interest * (1.5 if n_interests > 1 else 1.0))
        if a.rating is not None:
            confidence = min(1.0, (a.rating_count or 0) / 50.0)
            rating = (a.rating / 5.0) * (0.5 + 0.5 * confidence)
        else:
            rating = 0.3
        if a.price is None:
            price = 0.4
        elif pmax == pmin:
            price = 1.0
        else:
            price = 1.0 - (float(a.price) - pmin) / (pmax - pmin)
        evidence = 0.0
        evidence += 0.5 if a.opening_hours.open_time and a.opening_hours.close_time else 0.0
        evidence += 0.25 if a.price is not None else 0.0
        evidence += 0.25 if a.has_coordinates else 0.0
        if a.availability_status == AvailabilityStatus.AVAILABLE:
            evidence = min(1.0, evidence + 0.25)

        score = 0.45 * interest + 0.25 * rating + 0.15 * price + 0.15 * evidence
        if is_must_include(a, request.must_include):
            score += 10.0
        a.relevance_score = round(score, 4)

    return sorted(activities, key=lambda x: (-(x.relevance_score or 0.0), x.activity_id))
