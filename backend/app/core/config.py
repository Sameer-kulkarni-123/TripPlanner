import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Trip Planning Agent"
    API_V1_STR: str = "/api/v1"
    
    # LiteAPI / Nuitee credentials
    NUITEE_API_KEY: str = ""
    NUITEE_API_BASE_URL: str = "https://api.liteapi.travel/v3.0"
    
    # LLM Settings (can be OpenAI, Google Gemini, Anthropic, or local)
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "gemini-1.5-pro"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
