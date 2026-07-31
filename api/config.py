"""Application configuration using Pydantic Settings."""

import os
from enum import StrEnum
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BeforeValidator, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    _version = version("become")
except PackageNotFoundError:
    _version = "0.0.0"


def _normalize_log_level(value: Any) -> Any:
    """Upper-case string log levels so lowercase env input still validates."""
    return value.upper() if isinstance(value, str) else value


# Accepted logging levels; an invalid LOG_LEVEL is rejected when settings load
# rather than crashing later inside logging.setLevel().
LogLevel = Annotated[
    Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    BeforeValidator(_normalize_log_level),
]

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


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", ""})


def _has_remote_cors_origin(origins: list[str]) -> bool:
    """Return whether any CORS origin targets a non-loopback (deployed) host.

    :param origins: Configured CORS origins.
    :return: True if at least one origin points at a remote host.
    """
    return any((urlparse(origin).hostname or "") not in _LOOPBACK_HOSTS for origin in origins)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and dotenv files."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Deployment profile and test-runner flag (two independent axes)
    environment: Environment = Environment.DEV
    testing: bool = Field(default=False, validation_alias="TESTING")

    # Set by Railway on every deployed service, absent locally and in CI. Used to
    # decide whether the dev profile is a laptop or an internet-reachable service:
    # the dev deploy has its own database and public URL, so it has to satisfy the
    # same invariants as staging and production.
    railway_environment_name: str | None = Field(
        default=None, validation_alias="RAILWAY_ENVIRONMENT_NAME"
    )

    # Database
    database_url: str = "sqlite:///./become.db"

    # Privileged URL used only by Alembic for schema changes (DDL). When unset it
    # falls back to database_url, so the running app can use a least-privilege
    # role while migrations run as a privileged role.
    migration_database_url: str | None = None

    # Key for the email tags in security logs (api/auth/logging.py). Falls back to
    # secret_key; set it separately to keep tags comparable across a secret rotation.
    log_hash_key: str | None = None

    # Auth
    secret_key: str  # Required, load from .env
    access_token_expire_minutes: int = 15  # Short-lived access token
    refresh_token_expire_days: int = 7  # Long-lived refresh token

    # API
    debug: bool = False
    api_version: str = _version

    # Logging
    log_level: LogLevel = "INFO"
    log_file: str | None = None

    # Observability (Sentry error tracking; disabled when unset)
    sentry_dsn: str | None = None

    # Better Stack log shipping (disabled unless both are set)
    betterstack_source_token: str | None = None
    betterstack_ingesting_host: str | None = None

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Public base URL of this API, used to build profile photo proxy links.
    api_public_url: str = "http://localhost:8000"

    # Cloudflare origin lock: shared secret that Cloudflare injects (via a Transform
    # Rule) as the X-Origin-Verify request header. When set, only requests carrying it
    # are trusted to have transited Cloudflare, so CF-Connecting-IP is honoured only for
    # them; direct hits on the bare origin are keyed under a single constant instead.
    # Leave unset where Cloudflare is not in front (local/dev/staging).
    cloudflare_origin_secret: str = ""

    # Shared revocation / rate-limit store. Empty -> in-memory (dev/test); required in prod.
    redis_url: str = ""

    # TTL for the cached user-profile snapshot; a short value bounds the cache-aside
    # staleness window (see the user-caching spec).
    user_cache_ttl_seconds: int = 60

    # Railway Storage Bucket (S3-compatible; photo upload disabled if not set).
    # Railway injects these when a bucket is attached to the service.
    bucket_name: str | None = None
    bucket_endpoint: str | None = None
    bucket_access_key_id: str | None = None
    bucket_secret_access_key: str | None = None
    bucket_region: str = "auto"

    # Email (transactional: password reset, account verification). When the
    # provider is "console" or the selected provider's credentials are unset, the
    # link is logged rather than sent, so the flow still works offline in dev/CI/tests.
    email_provider: Literal["console", "http"] = "console"
    email_from: str = "no-reply@become.app"
    email_from_name: str = "BeCoMe"
    # Public base URL of the FRONTEND, used to build email links.
    frontend_base_url: str = "http://localhost:5173"
    password_reset_token_ttl_minutes: int = 60
    # Longer than the password-reset window: an activation email is routinely opened
    # the next morning, while a password reset is something the user is actively
    # waiting for.
    email_verification_token_ttl_hours: int = 24
    # HTTP transactional provider (Resend-style API).
    email_api_key: str | None = None
    email_api_url: str = "https://api.resend.com/emails"

    # Kill switches for the registration email-address policy
    # (api/services/email_policy.py). Both default on; flip either to false via
    # a Railway env var -- no deploy needed -- if it starts rejecting real users.
    disposable_email_blocking_enabled: bool = True
    mx_check_enabled: bool = True

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

    @property
    def email_enabled(self) -> bool:
        """Check if a real email provider is fully configured.

        The console provider always returns False: it logs reset links instead
        of sending them, so it never counts as a real send.

        :return: True when the HTTP provider is selected and its API key is set.
        """
        if self.email_provider == "http":
            return bool(self.email_api_key)
        return False

    @model_validator(mode="after")
    def _validate_deploy_invariants(self) -> "Settings":
        """Reject development defaults on every deployed service.

        A strong secret, real PostgreSQL database, Redis-backed store, a real
        (non-loopback) CORS origin, a configured email provider, debug off, and an
        explicit migration URL are required on anything that serves real traffic,
        since those services share the rate-limit / revocation store and are reachable
        from the internet. The Cloudflare origin lock is required only in production,
        where the app sits behind Cloudflare.

        :return: The validated settings instance.
        :raises ValueError: If a deployed profile still carries a development
            default, lacks a real email provider, runs with debug on, has no
            migration URL, or production lacks the Cloudflare origin secret.
        """
        # Environment.TEST doubles as the pytest-runner profile (the conftests set
        # APP_ENV=test with TESTING=1 and weak throwaway secrets), so its invariants
        # apply only to the real deployed staging, where TESTING is unset. Production
        # is never used by the test runner, so it is always enforced. The dev profile
        # counts too when it runs on Railway: that service has its own database and a
        # public URL, so "dev" there means the data is separate, not that the service
        # may be weakly configured. A laptop or a CI runner has no RAILWAY_* marker.
        is_deploy = self.environment is Environment.PROD or (
            not self.testing
            and (self.environment is Environment.TEST or self.railway_environment_name is not None)
        )
        if not is_deploy:
            return self

        profile = self.environment.value
        if (
            self.secret_key in _INSECURE_SECRET_KEYS
            or len(self.secret_key) < _MIN_SECRET_KEY_LENGTH
        ):
            raise ValueError(
                "secret_key must be a strong non-default value of at least "
                f"{_MIN_SECRET_KEY_LENGTH} characters in the {profile} profile"
            )
        if self.database_url.startswith("sqlite"):
            raise ValueError(f"SQLite is not allowed in the {profile} profile; use PostgreSQL")
        if not self.redis_url:
            raise ValueError(f"redis_url is required in the {profile} profile")

        if self.environment is Environment.PROD and not self.cloudflare_origin_secret:
            raise ValueError(
                "cloudflare_origin_secret is required in production so the client IP "
                "cannot be spoofed at the origin (Cloudflare injects X-Origin-Verify)"
            )
        if not _has_remote_cors_origin(self.cors_origins):
            raise ValueError(
                f"cors_origins must include the deployed frontend origin in the {profile} "
                "profile; the localhost defaults cannot serve real browser traffic"
            )
        if (urlparse(self.frontend_base_url).hostname or "") in _LOOPBACK_HOSTS:
            raise ValueError(
                f"frontend_base_url must point at the deployed frontend in the {profile} "
                "profile; every activation and password-reset link is built from it, so a "
                "loopback default mails out links nobody can open and no account can be "
                "activated"
            )
        if not self.email_enabled:
            raise ValueError(
                f"email_api_key is required in the {profile} profile with "
                "email_provider=http; without it the sender falls back to the console one, "
                "which delivers no mail and prints reset links to stdout instead"
            )
        if self.debug:
            raise ValueError(
                f"debug must be off in the {profile} profile; it turns on verbose "
                "framework output that does not belong on a service serving real traffic"
            )
        if not self.migration_database_url:
            raise ValueError(
                f"migration_database_url is required in the {profile} profile so Alembic "
                "runs as the privileged role and the app keeps its least-privilege one; "
                "set it explicitly even when it matches database_url"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    :return: Process-wide cached :class:`Settings` instance.
    """
    return Settings()
