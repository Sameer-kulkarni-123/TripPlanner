import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Trip Planning Agent"
    API_V1_STR: str = "/api/v1"
    
    # LiteAPI / Nuitee credentials
    NUITEE_API_KEY: str = ""
    NUITEE_API_BASE_URL: str = "https://api.liteapi.travel/v3.0"

    # Google Places API (New): destination search with landmarks, regions and "near X" queries.
    # Optional: without it, place search falls back to the free Open-Meteo geocoder.
    GOOGLE_MAPS_API_KEY: str = ""

    # Hotel Agent: max properties requested from /data/hotels per search (more = more budget stays found)
    HOTEL_SEARCH_MAX_HOTELS: int = 150
    # Hotel Agent: search radius around the destination's coordinates (regions/landmarks get the wider one)
    HOTEL_SEARCH_RADIUS_KM: float = 12
    HOTEL_SEARCH_REGION_RADIUS_KM: float = 35
    
    # LLM Settings. Providers are tried in LLM_PROVIDER_ORDER; a failing one hands over to the next.
    # Set e.g. "gemini" to use only Gemini, or "gemini,groq" to flip the order.
    LLM_PROVIDER_ORDER: str = "groq,gemini"
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "gemini-1.5-pro"
    # Gemini model used by app/integrations/gemini.py; the fallbacks are tried in order if a model is not found.
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_FALLBACK_MODELS: str = "gemini-3.5-flash-lite,gemini-2.5-flash"

    # Tavily web search: local tips from travellers (forums, Reddit, travel sites), summarised by Gemini
    TAVILY_API_KEY: str = ""

    # Itinerary Agent: ask Gemini for activity suggestions when live Nuitee experiences are unavailable
    ITINERARY_AI_ACTIVITIES: bool = True

    # Itinerary Agent: use offline demo activities when no live provider is configured
    ITINERARY_DEMO_MODE: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
