"""Local tips from travellers for a destination (Tavily web search + Gemini summary)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.insights.service import local_tips
from app.integrations.tavily import TavilyError

router = APIRouter()


class TipsRequest(BaseModel):
    city: str = Field(min_length=2, max_length=80)
    country: str = Field(default="", max_length=80)


@router.post("/local-tips")
async def get_local_tips(req: TipsRequest):
    """Scams, getting around, etiquette and other advice, each tip linked to the pages it came from."""
    try:
        return await local_tips(req.city.strip(), req.country.strip())
    except TavilyError as e:
        raise HTTPException(status_code=503, detail=str(e))
