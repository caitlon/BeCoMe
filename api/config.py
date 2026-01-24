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
    secret_key: str  # Required, load from .env
    access_token_expire_minutes: int = 15  # Short-lived access token
    refresh_token_expire_days: int = 7  # Long-lived refresh token

    # API
    debug: bool = False
    api_version: str = "0.1.0"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Supabase Storage (optional - photo upload disabled if not configured)
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_storage_bucket: str = "become-photos"

    @property
    def supabase_storage_enabled(self) -> bool:
        """Check if Supabase storage is properly configured."""
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
