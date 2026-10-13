"""Application configuration using Pydantic Settings."""

import ipaddress
import os
from enum import StrEnum
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import (
    BeforeValidator,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

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

    :cvar DEV: Local development. Debug off unless DEBUG is set, localhost CORS, SQLite allowed.
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


LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", ""})

# Each assistant model role that can run hosted: its provider setting, and the base URL
# setting a hosted role sends its requests to.
_ASSISTANT_PROVIDER_ROLES = (
    ("assistant_answer_provider", "assistant_answer_llm_base_url"),
    ("assistant_llm_provider", "assistant_llm_base_url"),
    ("assistant_embedding_provider", "assistant_embedding_base_url"),
)

# Railway environments the assistant may run in. An allowlist, so it fails closed: the real
# names are dev, test and prod, but before 2026-09-12 they were production and staging, and a
# renamed or preview environment (pr-123) must be refused rather than allowed.
_ASSISTANT_RAILWAY_ENVIRONMENTS = frozenset({"dev", "test"})

# The one LangSmith endpoint a deployed service may send traces to: the EU region.
_LANGSMITH_EU_ENDPOINT = "https://eu.api.smith.langchain.com"
# The project a laptop traces into by default; a deployed service must name its own.
_LANGSMITH_LOCAL_PROJECT = "become-assistant-local"
# What counts as "on" for a LangSmith library switch. The library takes only "true";
# the wider set refuses what a later library version or a habit might read as on.
_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})

# sslmode values under which libpq refuses to fall back to a connection in clear text.
_TLS_REQUIRING_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})

_POSTGRES_DEFAULT_PORT = 5432
_VECTOR_DB_DRIVERNAME = "postgresql+psycopg"
# libpq takes these from the query string ahead of the URL's own host, port and database.
_LIBPQ_TARGET_PARAMETERS = frozenset({"host", "hostaddr", "port", "dbname", "service"})


def _is_loopback_host(host: str) -> bool:
    """Return whether a URL host is "localhost" or any loopback IP address.

    :param host: Hostname as ``urlparse`` returns it (no brackets around an IPv6 address).
    :return: True for localhost and for every address in 127.0.0.0/8 or ::1.
    """
    host = host.rstrip(".")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _has_remote_cors_origin(origins: list[str]) -> bool:
    """Return whether any CORS origin targets a non-loopback (deployed) host.

    :param origins: Configured CORS origins.
    :return: True if at least one origin points at a remote host.
    """
    return any((urlparse(origin).hostname or "") not in LOOPBACK_HOSTS for origin in origins)


def _parse_postgres_url(url: str) -> URL | None:
    """Parse a database URL, accepting any PostgreSQL driver in its scheme.

    :param url: SQLAlchemy URL, such as ``postgresql+psycopg://...`` or ``postgresql://...``.
    :return: The parsed URL, or None when it is empty, malformed or not PostgreSQL.
        SQLAlchemy raises a plain ``ValueError`` for some malformed URLs (a password read
        as a port), and its text can carry the password, so both errors end here.
    """
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError):
        return None
    return parsed if parsed.get_backend_name() == "postgresql" else None


def _same_postgres_database(first: URL, second: URL) -> bool:
    """Compare two PostgreSQL URLs by the database they name, not by their spelling.

    The driver, the credentials and the query are ignored. The host is lower-cased and
    stripped of a trailing dot, and a missing port is 5432.

    :param first: Parsed PostgreSQL URL.
    :param second: Parsed PostgreSQL URL.
    :return: True when host, port and database name all match.
    """

    def identity(url: URL) -> tuple[str, int, str | None]:
        return (
            (url.host or "").lower().rstrip("."),
            url.port or _POSTGRES_DEFAULT_PORT,
            url.database,
        )

    return identity(first) == identity(second)


def _demands_tls(url: URL) -> bool:
    """Return whether a URL's ``sslmode`` stops libpq from falling back to clear text.

    :param url: Parsed PostgreSQL URL.
    :return: True for ``require``, ``verify-ca`` and ``verify-full``. A repeated parameter
        reaches libpq as a tuple it rejects, so it never counts as demanding TLS.
    """
    return url.query.get("sslmode") in _TLS_REQUIRING_SSLMODES


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

    # Email (transactional: account verification, password reset and the
    # existing-account notice). When the provider is "console" or the selected
    # provider's credentials are unset, nothing is sent: each link is logged with
    # its token cut to 8 characters and printed in full to stdout, so the flow
    # still works offline in dev/CI/tests.
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
    # a Railway env var, with no code change needed, if it starts rejecting real users.
    # The value takes effect when the process restarts (settings and the policy are
    # cached), which setting a Railway variable does by default.
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

    # AI assistant (RAG + read-only project explainer). Off everywhere by default;
    # _validate_assistant_deploy refuses to start production, or a Railway environment
    # other than dev and test, with it on, and on a deploy it demands every model role be
    # api. api/routes/assistant.py is registered only when this is true (see
    # api.main.create_app), so a service that leaves it off answers 404 for the whole
    # prefix.
    assistant_enabled: bool = False
    # The model for query transforms and index building: small and fast, so search stays
    # quick. The model that writes chat answers is the assistant_answer_llm_* pair below.
    assistant_llm_base_url: str = "http://127.0.0.1:8081/v1"
    assistant_llm_model: str = "Qwen/Qwen3-4B-Instruct-2507"
    # The model that writes the chat answers, on its own llama-server. The token cap bounds
    # one reply. The retrieval k is how many passages the chat endpoint's search returns (the
    # retrieval evaluation keeps its own k, RetrievalConfig.k).
    assistant_answer_llm_base_url: str = "http://127.0.0.1:8084/v1"
    assistant_answer_llm_model: str = "Qwen/Qwen3.5-9B"
    assistant_answer_max_tokens: int = Field(default=800, gt=0)
    assistant_retrieval_k: int = Field(default=3, gt=0)
    assistant_embedding_base_url: str = "http://127.0.0.1:8082/v1"
    assistant_embedding_model: str = "BAAI/bge-m3"
    # Where each of the three model roles runs: "local" is the llama-server named by the
    # role's base URL above, "api" is a hosted OpenAI-compatible endpoint at that same base
    # URL, paid for with assistant_api_key_ovh (OVHcloud, an EU provider). The roles switch
    # independently; the reranker has no hosted counterpart and always stays local.
    # _validate_assistant_providers refuses an api role with no key, a non-https URL or a
    # loopback host.
    assistant_answer_provider: Literal["local", "api"] = "local"
    assistant_llm_provider: Literal["local", "api"] = "local"
    assistant_embedding_provider: Literal["local", "api"] = "local"
    assistant_api_key_ovh: SecretStr | None = None
    # The value the hosted chat models send as reasoning_effort. "none" is what OVHcloud's
    # Qwen needs to answer at all; None sends nothing, for a provider that rejects the parameter.
    # An empty environment value means None.
    assistant_api_reasoning_effort: Literal["none", "low", "medium", "high"] | None = "none"
    assistant_rerank_base_url: str = "http://127.0.0.1:8083/v1"
    assistant_rerank_model: str = "BAAI/bge-reranker-v2-m3"
    # No default: a URL here would hard-code a password or reach a database that has none.
    assistant_vector_db_url: str = ""
    assistant_collection: str = "docs_markdown_headers_500_o10_captions_bge_m3"
    # workflow is the default because it is the only mode whose prompt and answers have
    # been measured; agent and hybrid, which give the model tools, stay selectable here.
    assistant_mode: Literal["agent", "workflow", "hybrid"] = "workflow"
    # The most tool calls one turn may make in agent and hybrid mode. It must be above
    # zero: an agent that can call nothing, or that always falls back, is a misconfiguration.
    assistant_max_tool_calls: int = Field(default=4, gt=0)
    # Limits the chat service and the chat route apply. The request schema
    # (api/schemas/assistant.py) holds the hard ceilings, 20 history entries (10 exchanges)
    # and 4000 characters per message, and rejects anything above them before the service
    # runs, so these can only lower them. The numbers are repeated here because this module
    # cannot import the schema without loading the assistant package in a deployed process;
    # a test keeps them equal.
    assistant_max_history_turns: int = Field(default=10, gt=0, le=10)
    assistant_max_message_chars: int = Field(default=4000, gt=0, le=4000)
    # Chat messages per user per fixed hour; 0 turns the limit off.
    assistant_rate_limit_per_hour: int = Field(default=60, ge=0)
    assistant_llm_timeout_seconds: float = 120.0
    # The longest one chat turn may take, fetching and generation together. When it runs
    # out, the call in flight is cancelled with the turn and the turn answers
    # "unavailable", so a stalled server does not hold the request past this deadline.
    # The model's own timeout above only bounds one request inside it.
    assistant_turn_timeout_seconds: float = Field(default=180.0, gt=0)
    assistant_private_corpus_dirs: list[str] = []
    # Path to a local-only JSON manifest describing the local corpus layer (see
    # api/assistant/rag/corpus.py::build_manifest). It sits at the root of a private
    # corpus kept outside this repository; its relative entries resolve from its own
    # folder, and every entry must resolve under one of assistant_private_corpus_dirs.
    # None means no local layer: the default, and what CI runs with. Tests that need a
    # local layer build one in a temporary folder and set this explicitly.
    assistant_private_corpus_manifest: str | None = None
    # Path to a JSON object mapping a chunk's key (enrich.chunk_key, the sha256 of the
    # chunk's own text) to a caption written for that chunk; only the "captions" context
    # mode reads it. It lives in the private corpus repository next to the local manifest,
    # so its version is part of corpus_version. A relative path resolves from the
    # repository root. None means no captions file, and a "captions" build then fails.
    assistant_captions_file: str | None = None
    # LangSmith tracing of the assistant, switched on by assistant_langsmith_enabled alone. With
    # it on, the full text of questions, tool replies and answers goes to the endpoint below,
    # so it needs a key (_validate_assistant_langsmith). It defaults to the EU endpoint, and
    # a deployed service may use only that one (_validate_assistant_deploy).
    assistant_langsmith_enabled: bool = False
    assistant_langsmith_api_key: SecretStr | None = None
    assistant_langsmith_endpoint: str = _LANGSMITH_EU_ENDPOINT
    assistant_langsmith_project: str = _LANGSMITH_LOCAL_PROJECT
    # The LangSmith library's own environment settings, read only so that a deployed service
    # can refuse them: the library honours them for any traced call, bypassing
    # assistant_langsmith_enabled. It reads the first non-blank of the four tracing switches
    # and sends a run to every destination in the two RUNS_ENDPOINTS lists, so each name is
    # kept apart rather than aliased: an alias would stop at a blank first name.
    langsmith_tracing_v2: str = ""
    langchain_tracing_v2: str = ""
    langsmith_tracing: str = ""
    langchain_tracing: str = ""
    langsmith_runs_endpoints: str = ""
    langchain_runs_endpoints: str = ""

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

        The console provider always returns False: for the verification, password
        reset and existing-account emails it logs each link masked and prints it in
        full to stdout instead of sending, so it never counts as a real send.

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

    @field_validator("assistant_api_reasoning_effort", mode="before")
    @classmethod
    def _empty_reasoning_effort_is_none(cls, value: object) -> object:
        """Map an empty or whitespace-only value to None, so the environment can send nothing."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("assistant_langsmith_endpoint")
    @classmethod
    def _clean_langsmith_endpoint(cls, value: str) -> str:
        """Strip surrounding whitespace and a trailing slash, so the client gets a clean URL."""
        return value.strip().rstrip("/")

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
    def _validate_assistant_deploy(self) -> "Settings":
        """Refuse the assistant in production, and on a deploy require hosted roles and a corpus DB.

        The assistant reads project data as the signed-in user and calls an LLM, so it may
        run on a laptop and on the dev and test services, never in production. Production
        is refused by profile and by Railway environment name, independently: APP_ENV=prod
        on Railway ``dev`` and APP_ENV=dev on Railway ``prod`` are both refused. The Railway
        name is checked against an allowlist, so an unknown or renamed environment is
        refused too. A deployed service has no llama-server to reach, so every model role
        there must be api; a laptop and a CI runner keep local roles. LangSmith tracing
        sends the text of questions, tool replies and answers, which is project data read
        as the signed-in user, to a third-party endpoint, so a deployed service may trace
        only to the EU endpoint, into a named project other than the local default, and only
        through assistant_langsmith_enabled: the library's own switches (``LANGSMITH_TRACING``
        and its variants) and its ``RUNS_ENDPOINTS`` lists are refused there. The corpus
        database must be its own: a non-empty
        assistant_vector_db_url, a ``postgresql+psycopg`` URL that names one host and a
        database, carries no host, hostaddr, port, dbname or service query override,
        names neither database_url nor migration_database_url, and has a single sslmode
        of require, verify-ca or verify-full, so the retrieval role cannot be pointed at
        the application's data or reach the corpus in clear text. The messages leave the
        URL out, because it carries a password. Keeping the guard here, right before
        _validate_deploy_invariants, means a deploy that sets ASSISTANT_ENABLED wrongly
        fails on this message first, rather than on whichever deploy invariant happens
        to be missing.

        is_deploy alone would not catch every case: it is False whenever TESTING is
        set, which is the pytest profile, so a Railway process that also carried
        TESTING=1 would pass the is_deploy check while still running on a deployed
        service. Checking railway_environment_name directly closes that gap -- a
        process on Railway is held to both rules, whatever else is set alongside it.

        :return: The validated settings instance.
        :raises ValueError: If assistant_enabled is true in the prod profile or on a
            Railway environment outside the allowlist, or on a deployed service while a
            model role is still local, assistant_langsmith_enabled is true with an
            endpoint other than the EU one or a blank or local-default project, a library
            tracing switch is on, a ``RUNS_ENDPOINTS`` list is set, assistant_vector_db_url is
            empty, not a ``postgresql+psycopg`` URL, without a database or a single host,
            carrying a host, hostaddr, port, dbname or service override, naming the same
            database as database_url or migration_database_url, or without a single sslmode
            of require, verify-ca or verify-full.
        """
        if not self.assistant_enabled:
            return self
        on_railway = self.railway_environment_name is not None
        railway_name = (self.railway_environment_name or "").strip().lower()
        if self.environment is Environment.PROD or (
            on_railway and railway_name not in _ASSISTANT_RAILWAY_ENVIRONMENTS
        ):
            raise ValueError(
                "assistant_enabled must stay false in production and in any Railway "
                f"environment other than dev and test (the {self.environment.value} profile "
                f"here, Railway environment {self.railway_environment_name!r})"
            )
        if self.is_deploy or on_railway:
            local_roles = [
                provider_name
                for provider_name, _ in _ASSISTANT_PROVIDER_ROLES
                if getattr(self, provider_name) != "api"
            ]
            if local_roles:
                raise ValueError(
                    f"{', '.join(local_roles)} must be api on a deployed service; a local "
                    "model server is not reachable there"
                )
            self._validate_assistant_langsmith_deploy()
            self._validate_assistant_corpus_database()
        return self

    def _validate_assistant_langsmith_deploy(self) -> None:
        """Hold LangSmith tracing on a deployed service to the EU endpoint and one switch.

        A library switch counts as on when it reads true, 1, yes or on, whatever its case.
        Messages name the field and never carry a key.

        :raises ValueError: If a library tracing switch is on, a ``RUNS_ENDPOINTS`` list is
            set, or tracing is on with an endpoint other than the EU one or a blank or
            local-default project.
        """
        switches = (
            self.langsmith_tracing_v2,
            self.langchain_tracing_v2,
            self.langsmith_tracing,
            self.langchain_tracing,
        )
        if any(value.strip().lower() in _TRUE_VALUES for value in switches):
            raise ValueError(
                "LANGSMITH_TRACING and its LANGCHAIN_ variants must not be true on a "
                "deployed service; use ASSISTANT_LANGSMITH_ENABLED instead"
            )
        if self.langsmith_runs_endpoints.strip() or self.langchain_runs_endpoints.strip():
            raise ValueError(
                "LANGSMITH_RUNS_ENDPOINTS and LANGCHAIN_RUNS_ENDPOINTS must not be set on a "
                "deployed service; they send traces to destinations outside the settings"
            )
        if not self.assistant_langsmith_enabled:
            return
        if self.assistant_langsmith_endpoint.lower() != _LANGSMITH_EU_ENDPOINT:
            raise ValueError(
                "assistant_langsmith_endpoint must be the EU endpoint on a deployed service"
            )
        project = self.assistant_langsmith_project.strip()
        if not project or project.lower() == _LANGSMITH_LOCAL_PROJECT:
            raise ValueError(
                "assistant_langsmith_project must be set to a project other than "
                f"{_LANGSMITH_LOCAL_PROJECT} when tracing is on on a deployed service"
            )

    def _validate_assistant_corpus_database(self) -> None:
        """Require a separate, TLS-protected corpus database on a deployed service.

        Messages never carry the URL or a part of it, since it holds the role's password.

        :raises ValueError: If assistant_vector_db_url is empty, not a
            ``postgresql+psycopg`` URL (the driver the vector store's engine needs),
            without a database name, carrying a libpq host, hostaddr, port, dbname or
            service parameter, without a host or with several, the same database as
            database_url or migration_database_url, or without a single ``sslmode`` of
            require, verify-ca or verify-full.
        """
        if not self.assistant_vector_db_url.strip():
            raise ValueError(
                "assistant_vector_db_url must be set on a deployed service; the corpus "
                "lives in its own PostgreSQL database with pgvector, not the application's"
            )
        vector_url = _parse_postgres_url(self.assistant_vector_db_url)
        if vector_url is None or vector_url.drivername != _VECTOR_DB_DRIVERNAME:
            raise ValueError(
                f"assistant_vector_db_url must be a {_VECTOR_DB_DRIVERNAME}:// URL naming the "
                "corpus database, with sslmode=require; the vector store's async engine "
                "connects through psycopg 3 only"
            )
        if not vector_url.database:
            raise ValueError(
                "assistant_vector_db_url must name the corpus database, as the path after "
                "the host and port"
            )
        if _LIBPQ_TARGET_PARAMETERS & vector_url.query.keys():
            raise ValueError(
                "assistant_vector_db_url must not carry host, hostaddr, port, dbname or "
                "service query parameters, which libpq lets override the URL; put the host, "
                "port and database in the URL itself"
            )
        if not vector_url.host or "," in vector_url.host:
            raise ValueError(
                "assistant_vector_db_url must name the corpus database host, one host, in "
                "the URL; libpq would otherwise fill it in from the environment or try "
                "several in turn"
            )
        for other in (self.database_url, self.migration_database_url or ""):
            other_url = _parse_postgres_url(other)
            if other_url is not None and _same_postgres_database(vector_url, other_url):
                raise ValueError(
                    "assistant_vector_db_url must not point at the database named by "
                    "database_url or migration_database_url; the corpus needs a database "
                    "of its own so the retrieval role never reaches application data"
                )
        if not _demands_tls(vector_url):
            raise ValueError(
                "assistant_vector_db_url must require TLS on a deployed service; add "
                "sslmode=require (or verify-ca, verify-full) to the URL once"
            )

    @model_validator(mode="after")
    def _validate_assistant_providers(self) -> "Settings":
        """Refuse a model role set to the hosted API that cannot safely reach it.

        A role in api mode sends every prompt, and the key, to its base URL. With no key
        the first request would fail with a 401 nobody reads at start-up. The URL must be
        https, so neither the key nor a prompt crosses the network in clear text; that also
        rules out every plain-http spelling of a local server in one check. A loopback host
        is refused on top of that, because an https loopback address would send the key to a
        local server that ignores it while the role looks hosted. A blank key counts as
        missing: ``ASSISTANT_API_KEY_OVH=`` in an env file arrives as an empty string. A
        role in local mode needs neither.

        :return: The validated settings instance.
        :raises ValueError: If a role is in api mode and assistant_api_key_ovh is missing
            or blank, or that role's base URL is not an https URL with a host, or its host
            is a loopback address.
        """
        key = self.assistant_api_key_ovh.get_secret_value() if self.assistant_api_key_ovh else ""
        for provider_name, url_name in _ASSISTANT_PROVIDER_ROLES:
            if getattr(self, provider_name) != "api":
                continue
            if not key.strip():
                raise ValueError(f"assistant_api_key_ovh must be set when {provider_name} is api")
            parsed = urlparse(getattr(self, url_name))
            if not parsed.scheme or not parsed.hostname:
                raise ValueError(
                    f"{url_name} must be an https:// URL with a host, the provider's "
                    f"OpenAI-compatible endpoint, when {provider_name} is api"
                )
            if parsed.scheme != "https":
                raise ValueError(f"{url_name} must use https when {provider_name} is api")
            if _is_loopback_host(parsed.hostname):
                raise ValueError(
                    f"{url_name} must not be a loopback address when {provider_name} is api"
                )
        return self

    @model_validator(mode="after")
    def _validate_assistant_langsmith(self) -> "Settings":
        """Refuse LangSmith tracing that has no API key to send it with.

        With tracing on and no key, every traced call would fail to reach LangSmith,
        and nothing would say so until somebody looked for the traces. A missing key
        is a configuration error, raised here, at start-up. A blank key counts as
        missing: ``ASSISTANT_LANGSMITH_API_KEY=`` in an env file arrives as an empty
        string. With tracing off the key is not needed.

        :return: The validated settings instance.
        :raises ValueError: If assistant_langsmith_enabled is true and
            assistant_langsmith_api_key is missing or blank.
        """
        key = self.assistant_langsmith_api_key
        if self.assistant_langsmith_enabled and not (key.get_secret_value() if key else "").strip():
            raise ValueError(
                "assistant_langsmith_api_key must be set when assistant_langsmith_enabled is true"
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
        if (urlparse(self.frontend_base_url).hostname or "") in LOOPBACK_HOSTS:
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
