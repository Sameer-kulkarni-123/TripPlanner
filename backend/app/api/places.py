"""Place search: any city, with coordinates, time zone and nearest airport."""
from fastapi import APIRouter, HTTPException, Query

from app.integrations.places import PlacesError, search_places

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
