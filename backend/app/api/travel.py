"""API router for travel and transport operations."""
from fastapi import APIRouter, HTTPException
from app.agents.travel.schemas import TravelSearchRequest, TravelSearchResult
from app.agents.travel.services.search import TransportSearchService

router = APIRouter()
search_service = TransportSearchService()


@router.post("/search", response_model=TravelSearchResult)
async def search_transport(request: TravelSearchRequest):
    """
    Search, filter, and deterministically rank transport options.
    """
    try:
        ranked_options = await search_service.search_and_rank(request)
        return TravelSearchResult(
            query=request,
            options=ranked_options,
            limitations=[]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
