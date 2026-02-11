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

    SQLite uses check_same_thread=False for FastAPI compatibility.
    PostgreSQL gets a tuned connection pool to stay within Supabase limits.

    :return: Configured SQLAlchemy Engine instance
    """
    settings = get_settings()
    connect_args: dict[str, bool] = {}
    pool_kwargs: dict[str, object] = {}

    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        # Keep the pool small to avoid hitting Supabase session-mode limits.
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
    """Create all tables defined in models.

    Call this on application startup to ensure database schema exists.
    """
    from api.db import models  # noqa: F401 — registers models with SQLModel.metadata

    SQLModel.metadata.create_all(get_engine())
