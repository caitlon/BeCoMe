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
    PostgreSQL uses connection pooling defaults.

    :return: Configured SQLAlchemy Engine instance
    """
    settings = get_settings()
    connect_args: dict[str, bool] = {}

    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.database_url,
        echo=settings.debug,
        connect_args=connect_args,
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
