"""API router for hotel / accommodation operations."""
from fastapi import APIRouter, HTTPException
from app.agents.hotel.schemas import HotelSearchRequest, HotelSearchResult
from app.agents.hotel.services.search import HotelSearchService

router = APIRouter()
search_service = HotelSearchService()


@router.post("/search", response_model=HotelSearchResult)
async def search_hotels(request: HotelSearchRequest):
    """
    Search, filter, and deterministically rank hotel room/rate options.
    """
    try:
        return await search_service.search(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
