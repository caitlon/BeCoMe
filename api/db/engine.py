"""Database engine setup and table creation.

This module provides lazy initialization of the database engine,
following the Dependency Inversion Principle (DIP).
"""

from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine

from api.config import get_settings


def _create_engine() -> Engine:
    """Create database engine based on settings.

    SQLite uses check_same_thread=False for FastAPI compatibility. PostgreSQL
    gets a tuned connection pool plus hardened connect arguments: required TLS,
    a connect timeout, an application name, and per-session statement and
    idle-in-transaction timeouts.

    :return: Configured SQLAlchemy Engine instance
    """
    settings = get_settings()
    connect_args: dict[str, object] = {}
    pool_kwargs: dict[str, object] = {}

    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        # Harden the PostgreSQL connection: require TLS on deployed databases
        # (test runs fall back to "prefer" for an ephemeral local Postgres
        # without SSL), fail fast on a slow connect, tag connections for
        # observability, and cap runaway work with per-session statement and
        # idle-in-transaction timeouts (milliseconds) so a single query cannot
        # exhaust the managed database.
        connect_args = {
            "sslmode": "prefer" if settings.testing else "require",
            "connect_timeout": 10,
            "application_name": f"become-{settings.environment.value}",
            "options": "-c statement_timeout=30000 -c idle_in_transaction_session_timeout=60000",
        }
        # Keep the pool small to stay within the managed Postgres connection limit.
        # pool_pre_ping drops stale connections before reuse.
        pool_kwargs = {
            "pool_size": 3,
            "max_overflow": 2,
            "pool_recycle": 300,
            "pool_pre_ping": True,
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


def create_db_and_tables() -> None:
    """Create tables for SQLite and ephemeral test databases.

    Deployed PostgreSQL schemas are owned by Alembic migrations, so this is a
    no-op there: it avoids racing ``create_all`` across uvicorn workers and keeps
    migrations the single source of schema truth. SQLite (local development) and
    test runs (``TESTING=1``, including the e2e PostgreSQL) keep using
    ``create_all`` for a zero-setup, isolated schema.
    """
    from api.db import models  # noqa: F401 — registers models with SQLModel.metadata

    settings = get_settings()
    if not (settings.database_url.startswith("sqlite") or settings.testing):
        return
    SQLModel.metadata.create_all(get_engine())
