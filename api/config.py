"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite:///./become.db"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_hours: int = 24

    # API
    debug: bool = False
    api_version: str = "0.1.0"

    # CORS
    cors_origins: list[str] = [
        "https://*.lovable.app",
        "http://localhost:3000",
    ]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
