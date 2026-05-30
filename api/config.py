"""Application configuration using Pydantic Settings."""

import os
from enum import StrEnum
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    _version = version("become")
except PackageNotFoundError:
    _version = "0.0.0"

# Secret values rejected in production (development defaults must never ship).
_INSECURE_SECRET_KEYS = frozenset({"", "changeme", "test-secret-key", "test-secret-key-for-ci"})

# Shortest secret accepted in production (openssl rand -hex 32 yields 64 characters).
_MIN_SECRET_KEY_LENGTH = 32

_APP_ENV_VAR = "APP_ENV"


class Environment(StrEnum):
    """Deployment environment profile.

    :cvar DEV: Local development. Debug on, permissive CORS, SQLite allowed.
    :cvar TEST: Deployed staging for manual QA. Debug off, rate limiting on.
    :cvar PROD: Production. Strict secret and database validation enforced.
    """

    DEV = "dev"
    TEST = "test"
    PROD = "prod"


def _resolve_environment() -> Environment:
    """Resolve the active profile from the ``APP_ENV`` variable.

    ``APP_ENV`` is the single environment selector. When it is unset, the local
    development profile is assumed. Setting the conventional ``ENVIRONMENT``
    variable instead is rejected with a clear error rather than silently ignored.

    :return: Resolved environment profile.
    :raises ValueError: If ``APP_ENV`` holds a value outside the enum, or if
        ``ENVIRONMENT`` is set while ``APP_ENV`` is not.
    """
    raw = os.environ.get(_APP_ENV_VAR)
    if raw is None:
        stray = os.environ.get("ENVIRONMENT")
        if stray:
            raise ValueError(f"Select the profile with APP_ENV, not ENVIRONMENT (got {stray!r})")
        return Environment.DEV
    return Environment(raw.strip().lower())


def _env_files_for(environment: Environment) -> tuple[str, ...]:
    """Build the ordered dotenv list for a profile.

    The base ``.env`` loads first and the per-environment ``.env.<env>`` file
    loads second, so profile-specific values override the shared base.

    :param environment: Active environment profile.
    :return: Ordered tuple of dotenv paths (later entries override earlier).
    """
    return (".env", f".env.{environment.value}")


class Settings(BaseSettings):
    """Application settings loaded from environment variables and dotenv files."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Deployment profile and test-runner flag (two independent axes)
    environment: Environment = Environment.DEV
    testing: bool = Field(default=False, validation_alias="TESTING")

    # Database
    database_url: str = "sqlite:///./become.db"

    # Privileged URL used only by Alembic for schema changes (DDL). When unset it
    # falls back to database_url, so the running app can use a least-privilege
    # role while migrations run as a privileged role.
    migration_database_url: str | None = None

    # Auth
    secret_key: str  # Required, load from .env
    access_token_expire_minutes: int = 15  # Short-lived access token
    refresh_token_expire_days: int = 7  # Long-lived refresh token

    # API
    debug: bool = False
    api_version: str = _version

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Public base URL of this API, used to build profile photo proxy links.
    api_public_url: str = "http://localhost:8000"

    # Railway Storage Bucket (S3-compatible; photo upload disabled if not set).
    # Railway injects these when a bucket is attached to the service.
    bucket_name: str | None = None
    bucket_endpoint: str | None = None
    bucket_access_key_id: str | None = None
    bucket_secret_access_key: str | None = None
    bucket_region: str = "auto"

    def __init__(self, **kwargs: Any) -> None:
        """Load ``.env`` then ``.env.<APP_ENV>`` and inject the resolved profile.

        The profile is resolved from ``APP_ENV`` and passed as an init argument,
        which takes precedence over the implicit ``ENVIRONMENT`` variable so
        ``APP_ENV`` stays the only selector.

        :param kwargs: Keyword settings forwarded to the base settings model.
        """
        resolved = _resolve_environment()
        kwargs.setdefault("environment", resolved)
        super().__init__(_env_file=_env_files_for(resolved), **kwargs)

    @property
    def storage_enabled(self) -> bool:
        """Check if Railway bucket storage is fully configured.

        :return: True when the bucket name, endpoint, and both credentials are set.
        """
        return bool(
            self.bucket_name
            and self.bucket_endpoint
            and self.bucket_access_key_id
            and self.bucket_secret_access_key
        )

    @model_validator(mode="after")
    def _validate_production_invariants(self) -> "Settings":
        """Reject insecure development defaults when running in production.

        :return: The validated settings instance.
        :raises ValueError: If production uses an insecure secret or SQLite.
        """
        if self.environment is Environment.PROD:
            if (
                self.secret_key in _INSECURE_SECRET_KEYS
                or len(self.secret_key) < _MIN_SECRET_KEY_LENGTH
            ):
                raise ValueError(
                    "secret_key must be a strong non-default value of at least "
                    f"{_MIN_SECRET_KEY_LENGTH} characters in production"
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not allowed in production; use PostgreSQL")
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    :return: Process-wide cached :class:`Settings` instance.
    """
    return Settings()
