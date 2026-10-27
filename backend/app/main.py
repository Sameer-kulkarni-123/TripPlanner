"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.travel import router as travel_router
from app.api.itinerary import router as itinerary_router
from app.api.hotel import router as hotel_router
from app.api.places import router as places_router
from app.api.assistant import router as assistant_router
from app.api.insights import router as insights_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Multi-Agent AI Trip Planning Backend"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(travel_router, prefix=f"{settings.API_V1_STR}/travel", tags=["Travel"])
app.include_router(itinerary_router, prefix=f"{settings.API_V1_STR}/itinerary", tags=["Itinerary"])
app.include_router(hotel_router, prefix=f"{settings.API_V1_STR}/hotel", tags=["Hotel"])
app.include_router(places_router, prefix=f"{settings.API_V1_STR}/places", tags=["Places"])
app.include_router(assistant_router, prefix=f"{settings.API_V1_STR}/assistant", tags=["Assistant"])
app.include_router(insights_router, prefix=f"{settings.API_V1_STR}/insights", tags=["Local tips"])


@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "0.1.0",
        "gemini_configured": bool(settings.GEMINI_API_KEY.strip()),
        "nuitee_configured": bool(settings.NUITEE_API_KEY.strip()),
        "tavily_configured": bool(settings.TAVILY_API_KEY.strip()),
    }
