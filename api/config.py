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


# Verbosity used when LOG_LEVEL is not set. Development wants every DEBUG trace;
# the deployed profiles stay at INFO, where the drain is affordable and the records
# carry no detail that only helps a developer sitting at a keyboard.
_DEFAULT_LOG_LEVELS: dict[Environment, LogLevel] = {
    Environment.DEV: "DEBUG",
    Environment.TEST: "INFO",
    Environment.PROD: "INFO",
}


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

    # Database. The SQLite fallback is deliberate and is not what local development is
    # meant to use: it exists so the app boots with nothing installed. The intended local
    # setup is the PostgreSQL in docker/docker-compose.yml, which env/.env.example points at,
    # because Alembic targets PostgreSQL and SQLite reaches the schema through create_all
    # instead. Every deployed environment sets this explicitly, so the default is only
    # ever seen locally.
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

    # Logging. The field default is only a floor: when LOG_LEVEL is absent,
    # _apply_profile_log_level replaces it with the active profile's level from
    # _DEFAULT_LOG_LEVELS.
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
    # a Railway env var, with no deploy needed, if it starts rejecting real users.
    disposable_email_blocking_enabled: bool = True
    mx_check_enabled: bool = True

    # Cloudflare Turnstile bot check on the unauthenticated auth endpoints
    # (api/auth/turnstile.py). Off by default so a fresh clone, local development, and
    # the test suite all run with no widget and no secret. Every deployed service is
    # meant to switch it on, and turnstile_enabled doubles as the kill switch for a
    # siteverify outage, so a deploy that leaves it off starts and is reported at ERROR
    # (api/main.py) rather than refused. turnstile_hostnames lists the frontend hosts a
    # token may be minted on, in the JSON-array form cors_origins uses; a token naming
    # anything else is refused, so an empty list refuses everything. Hostnames are
    # matched case-insensitively, as DNS names compare.
    turnstile_enabled: bool = False
    turnstile_secret_key: str = ""
    turnstile_hostnames: list[str] = []

    # Local AI assistant (RAG + read-only project explainer). Off everywhere by
    # default; _validate_assistant_local_only refuses to start any deployed profile
    # with it on, so turning it on is only ever a developer's own choice on their own
    # machine. api/routes/assistant.py is registered only when this is true (see
    # api.main.create_app), so a deployed service answers 404 for the whole prefix
    # regardless of this validator.
    assistant_enabled: bool = False
    assistant_llm_base_url: str = "http://127.0.0.1:8081/v1"
    assistant_llm_model: str = "Qwen/Qwen3-4B-Instruct-2507"
    assistant_embedding_base_url: str = "http://127.0.0.1:8082/v1"
    assistant_embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    assistant_rerank_base_url: str = "http://127.0.0.1:8083/v1"
    assistant_rerank_model: str = "BAAI/bge-reranker-v2-m3"
    # Local-only and passwordless: the assistant-db service trusts connections from 127.0.0.1.
    assistant_vector_db_url: str = "postgresql+psycopg://assistant@127.0.0.1:5433/assistant"
    assistant_collection: str = "docs_default"
    assistant_mode: Literal["agent", "workflow", "hybrid"] = "hybrid"
    assistant_max_tool_calls: int = 4
    assistant_max_history_turns: int = 10
    assistant_max_message_chars: int = 4000
    assistant_rate_limit_per_hour: int = 60
    assistant_llm_timeout_seconds: float = 120.0
    assistant_private_corpus_dirs: list[str] = []
    assistant_langsmith_enabled: bool = False
    assistant_langsmith_api_key: str | None = None
    assistant_langsmith_endpoint: str = "https://eu.api.smith.langchain.com"
    assistant_langsmith_project: str = "become-assistant-local"

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

    @property
    def is_deploy(self) -> bool:
        """Check whether this process is a deployed service rather than a laptop.

        A deployed service has its own database, a public URL, and shares the
        rate-limit / revocation store, so it must satisfy the invariants in
        :meth:`_validate_deploy_invariants` and may not trust client-supplied
        forwarding headers.

        ``Environment.TEST`` doubles as the pytest-runner profile (the conftests set
        ``APP_ENV=test`` with ``TESTING=1`` and weak throwaway secrets), so it counts
        only when ``TESTING`` is unset, as on the real staging deploy. Production is
        never used by the test runner, so it always counts. The dev profile counts
        when it runs on Railway: that service has its own database and a public URL,
        so "dev" there means the data is separate, not that the service may be weakly
        configured. A laptop or a CI runner carries no ``RAILWAY_*`` marker.

        :return: True when this process serves real traffic on a deployed service.
        """
        return self.environment is Environment.PROD or (
            not self.testing
            and (self.environment is Environment.TEST or self.railway_environment_name is not None)
        )

    @model_validator(mode="after")
    def _apply_profile_log_level(self) -> "Settings":
        """Fall back to the active profile's log level when ``LOG_LEVEL`` is unset.

        Without this, a service whose variable was never set runs at the field default,
        whether that is a new deploy, a cleared value, or a fresh clone, and development
        silently loses every DEBUG trace it is supposed to emit.

        An explicit value always wins: pydantic-settings records anything sourced
        from the environment or a dotenv file in ``model_fields_set``, so only a
        genuinely absent ``LOG_LEVEL`` is replaced here.

        :return: The settings instance with ``log_level`` resolved.
        """
        if "log_level" not in self.model_fields_set:
            self.log_level = _DEFAULT_LOG_LEVELS[self.environment]
        return self

    @model_validator(mode="after")
    def _validate_assistant_local_only(self) -> "Settings":
        """Refuse to start with the assistant switched on anywhere but a laptop.

        The assistant reads project data as the signed-in user and calls a locally
        running LLM; neither belongs on a service that serves real traffic. Keeping
        the guard here, right before _validate_deploy_invariants, means a deploy that
        somehow set ASSISTANT_ENABLED fails on this message first, rather than on
        whichever deploy invariant happens to be missing.

        is_deploy alone would not catch every case: it is False whenever TESTING is
        set, which is the pytest profile, so a Railway process that also carried
        TESTING=1 would pass the is_deploy check while still running on a deployed
        service. Checking railway_environment_name directly closes that gap -- a
        process on Railway must never run the assistant, whatever else is set
        alongside it.

        :return: The validated settings instance.
        :raises ValueError: If assistant_enabled is true while this process is
            either a deployed service or running on Railway.
        """
        if self.assistant_enabled and (self.is_deploy or self.railway_environment_name is not None):
            raise ValueError(
                "assistant_enabled must stay false on a deployed service (the "
                f"{self.environment.value} profile here); the assistant runs only on "
                "a developer machine"
            )
        return self

    @model_validator(mode="after")
    def _validate_deploy_invariants(self) -> "Settings":
        """Reject development defaults on every deployed service.

        A strong secret, real PostgreSQL database, Redis-backed store, a real
        (non-loopback) CORS origin, a configured email provider, debug off, an
        explicit migration URL, and the Cloudflare origin lock are required on
        anything that serves real traffic, since those services share the rate-limit /
        revocation store and are reachable from the internet. Every deployed
        environment sits behind Cloudflare, so the origin lock is demanded of all of
        them rather than of production alone.

        The Turnstile bot check is the one setting checked for *consistency* rather
        than demanded: with it on, the secret and the hostname list must be there, or
        every request is refused for want of configuration. With it off, the deploy
        starts. The check is fail-closed, so a Cloudflare siteverify outage answers 403
        to every real user on all four guarded endpoints, and ``turnstile_enabled`` is
        the switch that ends such an outage without a revert and a redeploy. Refusing
        to boot would take that switch away. The state is not silent instead:
        :func:`api.main._report_disabled_bot_check` records it at ERROR when the
        service starts, which is what reaches Sentry and the log drain.

        :return: The validated settings instance.
        :raises ValueError: If a deployed profile still carries a development
            default, lacks a real email provider, runs with debug on, has no
            migration URL or Cloudflare origin secret, or runs the bot check
            without a secret and a hostname list.
        """
        if not self.is_deploy:
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

        if not self.cloudflare_origin_secret:
            raise ValueError(
                f"cloudflare_origin_secret is required in the {profile} profile so the "
                "client IP is read from a header only Cloudflare can set (it injects "
                "X-Origin-Verify). Without it every request through Cloudflare is keyed "
                "under the edge's own address, which collapses all callers into one "
                "rate-limit bucket, and a request that reaches the bare origin is keyed "
                "off a forwarding header the origin cannot vouch for"
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
        if self.turnstile_enabled and not self.turnstile_secret_key:
            raise ValueError(
                f"turnstile_secret_key is required in the {profile} profile; the check is "
                "on and without the secret every siteverify call is refused, so all four "
                "endpoints answer 403 to real users"
            )
        if self.turnstile_enabled and not self.turnstile_hostnames:
            raise ValueError(
                f"turnstile_hostnames must list the deployed frontend hosts in the "
                f"{profile} profile; a token naming a hostname outside the list is "
                "refused, so an empty list refuses every request"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    :return: Process-wide cached :class:`Settings` instance.
    """
    return Settings()
