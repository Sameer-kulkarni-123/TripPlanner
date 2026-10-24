"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.travel import router as travel_router
from app.api.itinerary import router as itinerary_router

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


@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "0.1.0"
    }
