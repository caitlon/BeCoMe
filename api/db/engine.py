"""Database engine setup and table creation.

This module provides lazy initialization of the database engine,
following the Dependency Inversion Principle (DIP).
"""

import logging
from functools import lru_cache

from sqlalchemy import Engine, text
from sqlalchemy.engine import URL, make_url
from sqlmodel import SQLModel, create_engine

from api.config import LOOPBACK_HOSTS, Settings, get_settings

logger = logging.getLogger("api.db.engine")


_LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1"})


def _query_entries(url: URL, key: str) -> list[str] | None:
    """Read a libpq list parameter from the URL query.

    :param url: Parsed database URL.
    :param key: Query parameter name, such as ``host`` or ``hostaddr``.
    :return: Every comma-separated entry across all repeats, or None if the
        parameter is absent.
    """
    value = url.query.get(key)
    if value is None:
        return None
    values = (value,) if isinstance(value, str) else value
    return [entry for item in values for entry in item.split(",")]


def _is_local_database(database_url: str) -> bool:
    """Check whether the driver will connect to this machine.

    libpq lets ``host`` and ``hostaddr`` in the query string override the URL
    host, so the query wins when it names one, and every entry must be local:
    failing closed on any other keeps a remote host from passing as a socket. A
    ``service`` key makes libpq read the host from ``pg_service.conf``, which
    cannot be seen from here, so it counts as remote.

    :param database_url: SQLAlchemy URL of the database.
    :return: True for loopback hosts and Unix sockets only, False for anything else.
    """
    url = make_url(database_url)
    if "service" in url.query:
        return False
    hostaddrs = _query_entries(url, "hostaddr")
    if hostaddrs is not None and not all(addr in _LOOPBACK_ADDRESSES for addr in hostaddrs):
        return False
    hosts = _query_entries(url, "host")
    if hosts is None:
        hosts = [url.host or ""]
    return all(host in LOOPBACK_HOSTS or host.startswith("/") for host in hosts)


def _requires_tls(settings: Settings) -> bool:
    """Decide whether a PostgreSQL connection must use TLS.

    A deployed service or any process on Railway always requires it, even with
    ``TESTING`` set. A test run otherwise only prefers it: CI service containers
    and the compose end-to-end stack reach a database without TLS under names
    like ``db``. Any other process requires it unless the database is local, so a
    laptop whose ``DATABASE_URL`` points at a deployed database keeps the
    encrypted connection while the docker-compose PostgreSQL, which has SSL off,
    still connects.

    Two limits follow from judging by the URL alone: a deployed database reached
    through a local port-forward or tunnel counts as local and gets ``prefer``,
    and a URL with no host defers to libpq's own defaults (``PGHOST``,
    ``PGHOSTADDR``, ``PGSERVICE``), which settings cannot see.

    :param settings: Application settings.
    :return: True when ``sslmode=require`` must be used, False for ``prefer``.
    """
    if settings.is_deploy or settings.railway_environment_name is not None:
        return True
    return not settings.testing and not _is_local_database(settings.database_url)


def _create_engine() -> Engine:
    """Create database engine based on settings.

    SQLite uses check_same_thread=False for FastAPI compatibility. PostgreSQL
    gets a tuned connection pool plus hardened connect arguments: a TLS mode (see
    :func:`_requires_tls`), a connect timeout, an application name, and per-session
    statement and idle-in-transaction timeouts.

    :return: Configured SQLAlchemy Engine instance
    """
    settings = get_settings()
    connect_args: dict[str, object] = {}
    pool_kwargs: dict[str, object] = {}

    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        # Harden the PostgreSQL connection: TLS is required unless the database is
        # a local one that may not offer it (see _requires_tls), fail fast on a slow
        # connect, tag connections for observability, and cap runaway work with
        # per-session statement and idle-in-transaction timeouts (milliseconds) so a
        # single query cannot exhaust the managed database.
        connect_args = {
            "sslmode": "require" if _requires_tls(settings) else "prefer",
            "connect_timeout": 10,
            "application_name": f"become-{settings.environment.value}",
            "options": "-c statement_timeout=30000 -c idle_in_transaction_session_timeout=60000",
            # TCP keepalives: the private Railway network can silently drop an idle
            # socket, which otherwise surfaces as a stalled first query. Keepalives
            # detect a dead connection promptly and complement pool_pre_ping (which
            # only checks at checkout).
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
        # Keep the pool small to stay within the managed Postgres connection limit.
        # pool_pre_ping drops stale connections before reuse; pool_timeout fails a
        # checkout after 10s instead of the 30s default, so pool exhaustion surfaces
        # as a clear error rather than a long hang that looks like a slow database.
        pool_kwargs = {
            "pool_size": 3,
            "max_overflow": 2,
            "pool_recycle": 300,
            "pool_pre_ping": True,
            "pool_timeout": 10,
        }

    return create_engine(
        settings.database_url,
        echo=settings.debug,
        connect_args=connect_args,
        **pool_kwargs,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Get or create database engine singleton.

    Uses lazy initialization to avoid creating engine at import time.
    The engine is cached and reused for all subsequent calls.

    :return: Database Engine instance
    """
    return _create_engine()


def warm_up_connection_pool() -> None:
    """Open one real connection at startup so the first request hits a warm pool.

    On a networked database the first connection pays the TCP, TLS, and auth
    cost; doing it during startup moves that off the first user request. This
    matters on Railway, where App Sleep makes cold starts recur. Skipped for
    SQLite and test runs (no meaningful connection latency, and the test suite
    manages its own engine). Never fatal: a transient database blip logs a
    warning and startup proceeds, so a brief DB outage cannot block a deploy.
    """
    settings = get_settings()
    if settings.database_url.startswith("sqlite") or settings.testing:
        return
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connection pool warmed up", extra={"event": "db_warmup"})
    except Exception:
        logger.warning(
            "Database pool warm-up failed; continuing startup",
            extra={"event": "db_warmup_failed"},
            exc_info=True,
        )


def create_db_and_tables() -> None:
    """Create tables for SQLite and ephemeral test databases.

    A PostgreSQL schema outside test runs, local or deployed, is owned by Alembic
    migrations, so this is a no-op there: it avoids racing ``create_all`` across
    uvicorn workers and keeps migrations the single source of schema truth. SQLite
    (the local fallback) and test runs (``TESTING=1``, including the e2e PostgreSQL)
    keep using ``create_all`` for a zero-setup, isolated schema.
    """
    from api.db import models  # noqa: F401, registers models with SQLModel.metadata

    settings = get_settings()
    if not (settings.database_url.startswith("sqlite") or settings.testing):
        return
    SQLModel.metadata.create_all(get_engine())
