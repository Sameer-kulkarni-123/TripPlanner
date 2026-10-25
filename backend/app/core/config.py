import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Trip Planning Agent"
    API_V1_STR: str = "/api/v1"
    
    # LiteAPI / Nuitee credentials
    NUITEE_API_KEY: str = ""
    NUITEE_API_BASE_URL: str = "https://api.liteapi.travel/v3.0"

    # Hotel Agent: max properties requested from /data/hotels per search
    HOTEL_SEARCH_MAX_HOTELS: int = 50
    
    # LLM Settings (can be OpenAI, Google Gemini, Anthropic, or local)
    OPENAI_API_KEY: str = ""
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
