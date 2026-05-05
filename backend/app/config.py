"""
Application settings loaded from environment variables / .env file.
Uses Pydantic BaseSettings for type-safe config with auto .env loading.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration — values are read from .env or OS environment."""

    # LLM provider keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # LLM selection
    llm_provider: str = "openai"        # "openai" or "anthropic"
    llm_model: str = "gemini-3-flash-preview"

    # ToolRoom ERP integration
    toolroom_api_url: str = "https://toolroom.saptasati.co.in"

    # CORS origins (comma-separated in .env, parsed here as a single string)
    allowed_origins: str = "http://localhost:5173"

    class Config:
        import os, sys
        env_file_encoding = "utf-8"
        if getattr(sys, 'frozen', False):
            env_file = os.path.join(os.path.dirname(sys.executable), ".env")
        else:
            env_file = ".env"


# Singleton instance — import this wherever settings are needed
settings = Settings()
