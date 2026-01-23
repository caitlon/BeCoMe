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

    # Redis (for token blacklist)
    redis_url: str | None = None  # e.g., redis://localhost:6379/0

    # API
    debug: bool = False
    api_version: str = "0.1.0"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Azure Blob Storage (optional - photo upload disabled if not configured)
    azure_storage_connection_string: str | None = None
    azure_storage_account_name: str | None = None
    azure_storage_account_key: str | None = None
    azure_storage_container_name: str = "become-photos"

    @property
    def azure_storage_enabled(self) -> bool:
        """Check if Azure storage is properly configured."""
        return bool(
            self.azure_storage_connection_string
            and self.azure_storage_account_name
            and self.azure_storage_account_key
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
