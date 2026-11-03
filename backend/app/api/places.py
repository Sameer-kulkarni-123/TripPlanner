"""Place search: any city, with coordinates, time zone and nearest airport."""
from fastapi import APIRouter, HTTPException, Query

from app.integrations.places import PlacesError, place_details, search_places, suggest_places

router = APIRouter()


@router.get("/search")
async def places_search(q: str = Query(..., min_length=2, description="City, state or region, e.g. 'Mysuru' or 'Goa'"),
                        count: int = Query(8, ge=1, le=20),
                        country: str | None = Query(None, min_length=2, max_length=2, description="Only this country"),
                        prefer: str | None = Query(None, min_length=2, max_length=2,
                                                   description="Rank this country higher, e.g. the traveller's home")):
    """Geocode a city, state or region (Open-Meteo / GeoNames) and attach the airport to fly into (LiteAPI IATA list).
    If nothing matches, Gemini suggests what was meant and each suggestion is checked against the geocoder."""
    try:
        return {"query": q, "results": await search_places(q, count, country, prefer=prefer)}
    except PlacesError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/autocomplete")
async def places_autocomplete(q: str = Query(..., min_length=2),
                              session: str | None = Query(None, max_length=64,
                                                          description="Same token for every keystroke and the details call"),
                              prefer: str | None = Query(None, min_length=2, max_length=2),
                              count: int = Query(8, ge=1, le=10)):
    """Type-ahead for the place picker. With Google configured, returns `suggestions` (resolve the picked one
    with /places/details) plus ready `results` for generic queries like "hill stations near Bengaluru"."""
    try:
        return {"query": q, **await suggest_places(q, session=session, prefer=prefer, count=count)}
    except PlacesError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/details")
async def places_details(place_id: str = Query(..., min_length=3, max_length=300),
                         session: str | None = Query(None, max_length=64)):
    """Coordinates, time zone and airport for a Google place picked from /places/autocomplete."""
    try:
        return await place_details(place_id, session=session)
    except PlacesError as e:
        raise HTTPException(status_code=502, detail=str(e))
